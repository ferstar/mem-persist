# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mem-persist** is a Claude Code skill that saves conversation threads to a remote Nowledge Mem server via HTTP API. It solves the problem where MCP's `thread_persist` tool cannot access local session files when the MCP server is deployed remotely (e.g., via Tailscale).

**Version 2.0**: Pure Python implementation using Click CLI framework and `uv` for dependency management.

**Key Architecture**: Client-side execution → reads local session files → converts format → HTTP POST to remote API → stores in knowledge graph database.

## Development Commands

### Environment Setup

```bash
# Dependencies are auto-managed by uv
# No manual installation needed

# Run CLI directly
uv run mem-persist --help
```

### Running Commands

**Save current session**:
```bash
uv run python -m mem_persist save

# With custom title
uv run python -m mem_persist save --title "Implemented feature X"

# From specific project
uv run python -m mem_persist save --project-path /path/to/project

# Debug mode
uv run python -m mem_persist save --debug
```

**Run diagnostics**:
```bash
uv run python -m mem_persist diagnose
```

### Testing

```bash
# Test with debug output
uv run python -m mem_persist save --debug

# Test with custom config
MEM_API_URL=http://localhost:14243 \
MEM_AUTH_TOKEN=test \
uv run python -m mem_persist save --title "Test"

# Test diagnostics
uv run python -m mem_persist diagnose

# Run as Python module (alternative)
python -m mem_persist save
```

### Configuration

**Using .env file** (recommended):

Create a `.env` file in project root:
```bash
MEM_API_URL=http://100.64.0.184:14243
MEM_AUTH_TOKEN=helloworld
MAX_MESSAGES=0
```

**Environment variables**:
- `MEM_API_URL`: API endpoint (default: `http://100.64.0.184:14243`)
- `MEM_AUTH_TOKEN`: Bearer token (default: `helloworld`)
- `MAX_MESSAGES`: Message limit, 0=unlimited (default: 0)

**Priority** (highest to lowest):
1. Shell environment variables
2. Variables from `.env` file (searched in current dir and parents)
3. Default values

The `.env` file is automatically loaded by `python-dotenv` when running commands.

## Architecture

### Session Discovery

Claude Code CLI stores sessions in: `~/.claude/projects/-<path>/<session>.jsonl`

**Path encoding rules**:
- `/.` → `--` (hidden directories like `.claude`, `.config`)
- `/` → `-` (regular directories)

**Examples**:
- `/home/user/project` → `-home-user-project`
- `/home/user/.claude/skills` → `-home-user--claude-skills`
- `/root/.ssh/keys` → `-root--ssh-keys`

**Implementation**: `mem_persist.session.find_session_directory()`

### Data Flow

1. **Discovery**: `find_session_directory()` - Find session using path-to-dirname transformation
2. **Selection**: `find_latest_session()` - Get most recent `.jsonl` file (by mtime, ignore `agent-*.jsonl`)
3. **Parse**: `parse_session_file()` - Extract user/assistant messages from JSONL
4. **Transform**: `build_thread_request()` - Convert to Nowledge Mem API format
5. **Upload**: `APIClient.save_thread()` - POST to `/threads` with Bearer auth
6. **Verify**: Check HTTP 200/201 response

### API Request Format

```json
{
  "thread_id": "project_20251110_142918",
  "title": "Auto-generated or custom title",
  "messages": [
    {
      "role": "user|assistant",
      "content": "message text (max 15000 chars)",
      "timestamp": "ISO8601 timestamp"
    }
  ],
  "participants": ["user", "claude"],
  "source": "claude-code",
  "project": "project-name",
  "workspace": "/absolute/project/path",
  "metadata": {
    "session_file": "filename.jsonl",
    "total_lines_in_file": 123,
    "messages_extracted": 45,
    "persist_method": "uv_run_python"
  }
}
```

## Code Structure

### Python Package (`mem_persist/`)

**`config.py`**:
- `Config` dataclass for configuration management
- `Config.from_env()` loads from environment variables

**`session.py`**:
- `find_session_directory(project_path)`: Locate session dir using path encoding
- `find_latest_session(session_dir)`: Get most recent session file
- `parse_session_file(session_file, max_messages)`: Parse JSONL and extract messages
- `build_thread_request(...)`: Build API request payload
- `SessionNotFoundError`: Custom exception for missing sessions

**`api.py`**:
- `APIClient`: HTTP client using httpx
- `APIClient.health_check()`: Test API connectivity
- `APIClient.save_thread(payload)`: Upload thread data
- `APIError`: Custom exception for API failures

**`diagnostics.py`**:
- `run_diagnostics(config)`: Run all diagnostic checks
- Checks: API connectivity, authentication, session files, Python version
- Colored output for user-friendly reports

**`cli.py`**:
- Click-based CLI with two commands: `save` and `diagnose`
- Handles errors gracefully with colored output
- `--debug` flag for full tracebacks

### Key Design Patterns

1. **Separation of Concerns**: Each module has a single responsibility
2. **Type Hints**: Modern Python type annotations throughout
3. **Error Handling**: Custom exceptions with descriptive messages
4. **Configuration**: Environment-based, no hardcoded values
5. **Zero Dependencies**: Only `httpx` and `click` required

## Skill Integration

This is a **Claude Code Agent Skill** following best practices:

1. ✅ **Pure Python**: No shell scripts, easier to maintain and test
2. ✅ **Single command**: `uv run mem-persist save` does everything
3. ✅ **Progressive disclosure**: Concise SKILL.md → detailed README → comprehensive docs
4. ✅ **Environment-based config**: No hardcoded values
5. ✅ **Diagnostic tooling**: Built-in `diagnose` command
6. ✅ **Type-safe**: Modern Python with type hints

### When Claude Should Use This Skill

Trigger on user requests like:
- "保存当前thread" / "save current thread"
- "保存这个会话" / "save this session"
- "持久化当前对话" / "persist current conversation"
- "备份当前会话" / "backup this session"

**Invocation from another project**:
```bash
# Get current working directory from <env> block
PROJECT_PATH=/actual/project/path uv run python -m mem_persist save
```

**IMPORTANT**: When this skill is invoked from another project, you MUST pass the actual project path via `PROJECT_PATH` environment variable. Use the working directory from the `<env>` block, NOT the skill's own directory.

**Example**:
```bash
# If <env> shows: Working directory: /home/user/my-app
PROJECT_PATH=/home/user/my-app uv run python -m mem_persist save
```

## Important Notes

### Session File Format

Claude Code CLI uses **JSONL** (JSON Lines) format:
- One JSON object per line
- Each line is a complete event: `{"type": "user", "message": {...}, "timestamp": "..."}`
- Only `type: user|assistant` lines contain conversational messages
- Other types (e.g., tool calls) are filtered out

### Content Cleaning

The parser removes control characters (except `\n`, `\r`, `\t`) to ensure valid JSON and prevent API issues. Content is truncated at 15,000 characters per message.

### Error Handling

- Custom exceptions: `SessionNotFoundError`, `APIError`
- Graceful degradation with helpful error messages
- `--debug` flag shows full tracebacks for troubleshooting

### Dependencies

Runtime dependencies (minimal):
- **python**: 3.10+ required
- **httpx**: HTTP client
- **click**: CLI framework
- **uv**: Dependency manager (automatically handles installation)

No build step required; `uv run` handles everything.

## Extending to Other Tools

To support Cursor, Codex, or other AI coding tools:

1. Update `find_session_directory()` in `session.py` with new path patterns
2. Add format-specific parsers in `parse_session_file()` if JSON structure differs
3. Update `source` field in `build_thread_request()` to identify the tool
4. Test with actual session files from the new tool

All logic is in Python modules, making extensions straightforward.

## Common Issues

**"Session directory not found"**: Claude Code hasn't created session files yet, or wrong project directory. Check `~/.claude/projects/` for the encoded path. Verify project path is correct.

**"API connection failed"**: Server not running, wrong URL, or network issues. Run `diagnose` command to check connectivity. Verify `MEM_API_URL` is accessible.

**"Authentication failed"**: Wrong token or token expired. Verify `MEM_AUTH_TOKEN` environment variable. Test with `curl` to isolate the issue.

**"No session files found"**: No `.jsonl` files (excluding `agent-*.jsonl`) in session directory. Ensure Claude Code has created at least one session in this project.

**"Import errors"**: Dependencies not installed. Run `uv sync` or let `uv run` auto-install dependencies.
