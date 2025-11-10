"""Session discovery and parsing for Claude Code CLI"""

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
                msg_type = data.get("type")

                if msg_type not in ("user", "assistant"):
                    continue

                # Extract content from message structure
                content = _extract_content(data.get("message", {}))

                if content and len(content) > 5:
                    # Clean control characters (except \n \r \t)
                    clean_content = re.sub(
                        r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]',
                        '',
                        content[:15000]
                    )

                    messages.append({
                        "role": msg_type,
                        "content": clean_content,
                        "timestamp": data.get("timestamp"),
                    })
            except (json.JSONDecodeError, Exception):
                continue

    # Take most recent messages if limit is set
    if max_messages > 0 and len(messages) > max_messages:
        messages = messages[-max_messages:]

    return messages


def _extract_content(message_data: Any) -> str:
    """Extract text content from message data structure"""
    content = ""

    if isinstance(message_data, dict):
        content_blocks = message_data.get("content", [])

        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    content += block.get("text", "")
        elif isinstance(content_blocks, str):
            content = content_blocks
    elif isinstance(message_data, str):
        content = message_data

    return content


def build_thread_request(
    messages: list[dict[str, Any]],
    project_path: Path,
    session_file: Path,
    custom_title: str = "",
    total_lines: int = 0,
) -> dict[str, Any]:
    """Build API request payload for thread persistence

    Args:
        messages: List of parsed messages
        project_path: Project directory path
        session_file: Session file path (for metadata)
        custom_title: Optional custom thread title
        total_lines: Total lines in session file

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

    return {
        "thread_id": thread_id,
        "title": custom_title,
        "messages": messages,
        "participants": ["user", "claude"],
        "source": "claude-code",
        "project": project_name,
        "workspace": str(project_path.resolve()),
        "import_date": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "session_file": session_file.name,
            "total_lines_in_file": total_lines,
            "messages_extracted": len(messages),
            "persist_method": "uv_run_python",
        },
    }
