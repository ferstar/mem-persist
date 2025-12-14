"""Session discovery and parsing for Claude Code and Codex CLI"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MAX_CONTENT_LENGTH, MIN_CONTENT_LENGTH

logger = logging.getLogger(__name__)


class SessionNotFoundError(Exception):
    """Raised when session directory or files cannot be found"""
    pass


@dataclass
class ParseResult:
    """Result of parsing a session file

    Attributes:
        messages: List of parsed messages
        total_lines: Total lines in the file (avoid re-reading)
    """
    messages: list[dict[str, Any]]
    total_lines: int


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

    Raises:
        SessionNotFoundError: If session directory doesn't exist
    """
    abs_path = project_path.resolve()
    path_str = str(abs_path)

    # Apply encoding: "/." -> "--", "/" -> "-", strip leading "-"
    encoded = path_str.replace("/.", "--").replace("/", "-").lstrip("-")
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
    """Find the most recent session file in O(n) time

    Ignores agent-*.jsonl files which are sub-agent sessions.

    Raises:
        SessionNotFoundError: If no session files found
    """
    latest_file: Path | None = None
    latest_mtime: float = 0

    # O(n) scan - no sorting needed
    for f in session_dir.glob("*.jsonl"):
        if f.name.startswith("agent-"):
            continue

        try:
            mtime = f.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = f
        except OSError as e:
            logger.warning(f"Cannot stat {f}: {e}")
            continue

    if latest_file is None:
        raise SessionNotFoundError(f"No session files found in {session_dir}")

    return latest_file


def find_latest_session_for_project(
    project_path: Path,
    preferred_source: str = "auto",
) -> tuple[Path, str]:
    """Find latest session file for a project (Claude Code or Codex CLI)

    Args:
        project_path: Project directory path
        preferred_source: "auto", "claude", or "codex"

    Returns:
        Tuple of (session_file_path, source_name)

    Raises:
        SessionNotFoundError: If no sessions found for the project
    """
    preferred = (preferred_source or "auto").lower()
    if preferred not in {"auto", "claude", "codex"}:
        preferred = "auto"

    if preferred == "claude":
        claude_dir = find_session_directory(project_path)
        return find_latest_session(claude_dir), "claude-code"

    if preferred == "codex":
        return find_latest_codex_session(project_path), "codex"

    # Auto mode: try both and pick most recent
    errors: list[str] = []
    candidates: list[tuple[Path, float, str]] = []  # (path, mtime, source)

    try:
        claude_dir = find_session_directory(project_path)
        claude_latest = find_latest_session(claude_dir)
        candidates.append((
            claude_latest,
            claude_latest.stat().st_mtime,
            "claude-code",
        ))
    except SessionNotFoundError as exc:
        errors.append(str(exc))
    except OSError as e:
        errors.append(f"Cannot access Claude session: {e}")

    try:
        codex_latest = find_latest_codex_session(project_path)
        candidates.append((
            codex_latest,
            codex_latest.stat().st_mtime,
            "codex",
        ))
    except SessionNotFoundError as exc:
        errors.append(str(exc))
    except OSError as e:
        errors.append(f"Cannot access Codex session: {e}")

    if not candidates:
        raise SessionNotFoundError(
            "No session files found for project.\n" + "\n".join(errors)
        )

    # Pick by cached mtime - no extra stat() calls
    latest_file, _, source = max(candidates, key=lambda x: x[1])
    return latest_file, source


def parse_session_file(
    session_file: Path,
    max_messages: int = 0,
) -> ParseResult:
    """Parse JSONL session file and extract messages

    Args:
        session_file: Path to session JSONL file
        max_messages: Maximum messages to extract (0 = unlimited)

    Returns:
        ParseResult with messages and total line count
    """
    messages: list[dict[str, Any]] = []
    total_lines = 0

    with session_file.open("r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1

            # Skip if we have enough (will trim at end for most recent)
            if max_messages > 0 and len(messages) >= max_messages * 2:
                # Still count lines but don't parse
                continue

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                logger.debug(f"Skip invalid JSON at line {total_lines}: {e}")
                continue

            # Try Claude format first, then Codex
            parsed = _parse_claude_message(data) or _parse_codex_message(data)
            if not parsed:
                continue

            content = parsed["content"]
            if not content or len(content) <= MIN_CONTENT_LENGTH:
                continue

            # Clean control characters (except newline, carriage return, tab)
            clean_content = re.sub(
                r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]',
                '',
                content[:MAX_CONTENT_LENGTH],
            )

            messages.append({
                "role": parsed["role"],
                "content": clean_content,
                "timestamp": parsed.get("timestamp"),
            })

    # Take most recent messages if limit is set
    if max_messages > 0 and len(messages) > max_messages:
        messages = messages[-max_messages:]

    return ParseResult(messages=messages, total_lines=total_lines)


def _parse_claude_message(data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse Claude Code message structure

    Expected format:
        {"type": "user"|"assistant", "message": {...}, "timestamp": "..."}
    """
    msg_type = data.get("type")
    if msg_type not in ("user", "assistant"):
        return None

    content = _extract_content(data.get("message", {}))
    if not content:
        return None

    return {
        "role": msg_type,
        "content": content,
        "timestamp": data.get("timestamp"),
    }


def _parse_codex_message(data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse Codex CLI message structure

    Expected format:
        {"type": "response_item", "payload": {"type": "message", "role": "...", ...}}
    """
    if data.get("type") != "response_item":
        return None

    payload = data.get("payload", {})
    if payload.get("type") != "message":
        return None

    role = payload.get("role")
    if role not in ("user", "assistant"):
        return None

    content = _extract_content(payload)
    if not content:
        return None

    return {
        "role": role,
        "content": content,
        "timestamp": data.get("timestamp") or payload.get("timestamp"),
    }


def _extract_content(message_data: Any) -> str:
    """Extract text content from various message data structures

    Handles:
    - dict with "content" key containing list of blocks
    - dict with "content" key containing string
    - plain string
    - list of content blocks
    """
    if message_data is None:
        return ""

    if isinstance(message_data, str):
        return message_data

    if isinstance(message_data, list):
        # List of content blocks
        parts = []
        for block in message_data:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    if isinstance(message_data, dict):
        content_blocks = message_data.get("content", [])

        if isinstance(content_blocks, str):
            return content_blocks

        if isinstance(content_blocks, list):
            parts = []
            for block in content_blocks:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

    return ""


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
            title_content = first_user["content"][:80]
            custom_title = title_content + ("..." if len(first_user["content"]) > 80 else "")
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
    """Find the latest Codex CLI session file for a project in O(n) time

    Scans ~/.codex/sessions/ recursively and matches by cwd in session metadata.

    Raises:
        SessionNotFoundError: If no matching session found
    """
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        raise SessionNotFoundError(f"Codex sessions root not found: {sessions_root}")

    project_real = str(project_path.resolve())

    latest_file: Path | None = None
    latest_mtime: float = 0

    # O(n) scan with early termination on match
    for session_file in sessions_root.rglob("*.jsonl"):
        if not session_file.is_file():
            continue

        try:
            mtime = session_file.stat().st_mtime
        except OSError as e:
            logger.debug(f"Cannot stat {session_file}: {e}")
            continue

        # Only check cwd if this file is newer than current best
        if mtime <= latest_mtime:
            continue

        session_cwd = _extract_codex_cwd(session_file)
        if not session_cwd:
            continue

        try:
            if str(Path(session_cwd).resolve()) == project_real:
                latest_mtime = mtime
                latest_file = session_file
        except (OSError, ValueError) as e:
            logger.debug(f"Cannot resolve {session_cwd}: {e}")
            continue

    if latest_file is None:
        raise SessionNotFoundError(
            f"No Codex session files found for project: {project_real}"
        )

    return latest_file


def _extract_codex_cwd(session_file: Path) -> str | None:
    """Extract cwd from Codex session file metadata

    Reads only the first line of the file to get session_meta.
    """
    try:
        with session_file.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                return None

            data = json.loads(first_line)
            if data.get("type") != "session_meta":
                return None

            return data.get("payload", {}).get("cwd")

    except json.JSONDecodeError as e:
        logger.debug(f"Invalid JSON in {session_file}: {e}")
        return None
    except OSError as e:
        logger.debug(f"Cannot read {session_file}: {e}")
        return None
