"""Session discovery and parsing for Claude Code and Codex CLI"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionNotFoundError(Exception):
    """Raised when session directory or files cannot be found"""
    pass


def find_session_directory(project_path: Path) -> Path:
    """Find Claude Code CLI session directory using path encoding

    Claude Code CLI stores sessions in:
    ~/.claude/projects/-<encoded-path>/<session>.jsonl

    Path encoding rules:
    - /. -> -- (hidden directories)
    - /  -> -  (regular directories)

    Examples:
    - /home/user/project -> -home-user-project
    - /home/user/.claude/skills -> -home-user--claude-skills
    """
    # Convert absolute path to encoded dirname
    abs_path = project_path.resolve()
    path_str = str(abs_path)

    # Apply encoding rules:
    # 1. Replace "/." with "--" (for hidden directories like .claude)
    # 2. Replace remaining "/" with "-"
    # 3. Remove leading "/" if any
    encoded = path_str.replace("/.", "--").replace("/", "-").lstrip("-")

    # Ensure starts with single hyphen
    encoded = "-" + encoded

    projects_dir = Path.home() / ".claude" / "projects"
    session_dir = projects_dir / encoded

    if not session_dir.exists():
        raise SessionNotFoundError(
            f"Session directory not found: {session_dir}\n"
            f"Expected encoding for: {abs_path}\n"
            f"Make sure Claude Code has created sessions for this project."
        )

    return session_dir


def find_latest_session(session_dir: Path) -> Path:
    """Find the most recent session file (by modification time)

    Ignores agent-*.jsonl files which are sub-agent sessions.
    """
    session_files = [
        f for f in session_dir.glob("*.jsonl")
        if not f.name.startswith("agent-")
    ]

    if not session_files:
        raise SessionNotFoundError(
            f"No session files found in {session_dir}"
        )

    # Sort by modification time, most recent first
    latest = max(session_files, key=lambda f: f.stat().st_mtime)
    return latest


def find_latest_session_for_project(
    project_path: Path,
    preferred_source: str = "auto",
) -> tuple[Path, str]:
    """Find latest session file for a project (Claude Code or Codex CLI)

    Returns:
        (session_file_path, source_name)
    """
    preferred = (preferred_source or "auto").lower()
    if preferred not in {"auto", "claude", "codex"}:
        preferred = "auto"

    if preferred == "claude":
        claude_dir = find_session_directory(project_path)
        return find_latest_session(claude_dir), "claude-code"

    if preferred == "codex":
        return find_latest_codex_session(project_path), "codex"

    errors: list[str] = []
    candidates: list[tuple[Path, str]] = []

    try:
        claude_dir = find_session_directory(project_path)
        claude_latest = find_latest_session(claude_dir)
        candidates.append((claude_latest, "claude-code"))
    except SessionNotFoundError as exc:
        errors.append(str(exc))

    try:
        codex_latest = find_latest_codex_session(project_path)
        candidates.append((codex_latest, "codex"))
    except SessionNotFoundError as exc:
        errors.append(str(exc))

    if not candidates:
        raise SessionNotFoundError(
            "No session files found for project.\n" + "\n".join(errors)
        )

    latest_file, source = max(
        candidates,
        key=lambda pair: pair[0].stat().st_mtime,
    )
    return latest_file, source


def parse_session_file(
    session_file: Path,
    max_messages: int = 0
) -> list[dict[str, Any]]:
    """Parse JSONL session file and extract messages

    Args:
        session_file: Path to session JSONL file
        max_messages: Maximum messages to extract (0 = unlimited)

    Returns:
        List of message dicts with role, content, timestamp
    """
    messages = []

    with session_file.open("r", encoding="utf-8") as f:
        for line in f:
            # Skip early if we have enough messages (0 = no limit)
            if max_messages > 0 and len(messages) >= max_messages * 2:
                continue

            try:
                data = json.loads(line)
                parsed = _parse_claude_message(data) or _parse_codex_message(data)

                if not parsed:
                    continue

                content = parsed["content"]
                if content and len(content) > 5:
                    clean_content = re.sub(
                        r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]',
                        '',
                        content[:15000]
                    )

                    messages.append({
                        "role": parsed["role"],
                        "content": clean_content,
                        "timestamp": parsed.get("timestamp"),
                    })
            except (json.JSONDecodeError, Exception):
                continue

    # Take most recent messages if limit is set
    if max_messages > 0 and len(messages) > max_messages:
        messages = messages[-max_messages:]

    return messages


def _parse_claude_message(data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse Claude Code message structure"""
    msg_type = data.get("type")
    if msg_type not in ("user", "assistant"):
        return None

    content = _extract_content(data.get("message", {}))
    return {
        "role": msg_type,
        "content": content,
        "timestamp": data.get("timestamp"),
    }


def _parse_codex_message(data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse Codex CLI message structure"""
    if data.get("type") != "response_item":
        return None

    payload = data.get("payload", {})
    if payload.get("type") != "message":
        return None

    role = payload.get("role")
    if role not in ("user", "assistant"):
        return None

    content = _extract_content(payload)
    return {
        "role": role,
        "content": content,
        "timestamp": data.get("timestamp") or payload.get("timestamp"),
    }


def _extract_content(message_data: Any) -> str:
    """Extract text content from message data structure"""
    content = ""

    if isinstance(message_data, dict):
        content_blocks = message_data.get("content", [])

        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict):
                    text_val = block.get("text")
                    if isinstance(text_val, str):
                        content += text_val
        elif isinstance(content_blocks, str):
            content = content_blocks
    elif isinstance(message_data, str):
        content = message_data

    elif isinstance(message_data, list):
        for block in message_data:
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")

    return content


def build_thread_request(
    messages: list[dict[str, Any]],
    project_path: Path,
    session_file: Path,
    custom_title: str = "",
    total_lines: int = 0,
    source: str = "claude-code",
) -> dict[str, Any]:
    """Build API request payload for thread persistence

    Args:
        messages: List of parsed messages
        project_path: Project directory path
        session_file: Session file path (for metadata)
        custom_title: Optional custom thread title
        total_lines: Total lines in session file
        source: Session source identifier ("claude-code" or "codex")

    Returns:
        API request payload dict
    """
    project_name = project_path.name
    thread_id = f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Auto-generate title if not provided
    if not custom_title:
        first_user = next((m for m in messages if m["role"] == "user"), None)
        if first_user:
            custom_title = first_user["content"][:80]
            if len(first_user["content"]) > 80:
                custom_title += "..."
        else:
            custom_title = f"Claude Code Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    participants = ["user", "claude"] if source == "claude-code" else ["user", "codex"]

    return {
        "thread_id": thread_id,
        "title": custom_title,
        "messages": messages,
        "participants": participants,
        "source": source,
        "project": project_name,
        "workspace": str(project_path.resolve()),
        "import_date": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "session_file": session_file.name,
            "total_lines_in_file": total_lines,
            "messages_extracted": len(messages),
            "persist_method": "uv_run_python",
            "cli": source,
        },
    }


def find_latest_codex_session(project_path: Path) -> Path:
    """Find the latest Codex CLI session file for a project"""
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        raise SessionNotFoundError(
            f"Codex sessions root not found: {sessions_root}"
        )

    project_real = str(project_path.resolve())

    session_files = sorted(
        (f for f in sessions_root.rglob("*.jsonl") if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    for session_file in session_files:
        session_cwd = _extract_codex_cwd(session_file)
        if not session_cwd:
            continue

        try:
            if str(Path(session_cwd).resolve()) == project_real:
                return session_file
        except Exception:
            continue

    raise SessionNotFoundError(
        f"No Codex session files found for project: {project_real}"
    )


def _extract_codex_cwd(session_file: Path) -> str | None:
    """Extract cwd from Codex session file metadata"""
    try:
        with session_file.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                return None

            data = json.loads(first_line)
            if data.get("type") != "session_meta":
                return None

            payload = data.get("payload", {})
            return payload.get("cwd")
    except Exception:
        return None
