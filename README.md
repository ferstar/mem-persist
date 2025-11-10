# mem-persist Skill

Save Claude Code conversation threads to Nowledge Mem server via HTTP API.

**Version 1.0.0** - Pure Python implementation using `uv run`.

## Overview

This skill solves the remote MCP client problem described in [nowledge-mem#7](https://github.com/nowledge-co/nowledge-mem/issues/7) by using HTTP API instead of filesystem access.

### The Problem

The MCP `thread_persist` tool requires:
1. Direct filesystem access to session files
2. MCP server and client on same machine

This breaks when:
- MCP server is remote (e.g., via Tailscale or VPN)
- Client runs on different machine (laptop)
- Server cannot access client's local session files

### The Solution

This skill:
1. ✅ Runs locally on client machine (has filesystem access)
2. ✅ Reads Claude Code session files from project directory
3. ✅ Converts session format to Nowledge Mem API format
4. ✅ Sends data via HTTP API to remote server
5. ✅ Works with any network topology (local, VPN, Tailscale)

## Installation

**Already installed** at: `~/.claude/skills/mem-persist/`

Dependencies are managed by `uv`, no manual installation needed.

## Quick Start

```bash
# Save current session (from current directory)
uv run python -m mem_persist save

# With custom title
uv run python -m mem_persist save --title "Implemented auth feature"

# From specific project
uv run python -m mem_persist save --project-path /path/to/project

# Run diagnostics
uv run python -m mem_persist diagnose

# Get help
uv run python -m mem_persist --help
```

## Configuration

Environment variables can be set in three ways:

**1. Using .env file** (recommended):
```bash
# Copy the example file
cp .env.example .env

# Edit with your values
vim .env
```

Example `.env` file:
```bash
MEM_API_URL=http://your-server:14243
MEM_AUTH_TOKEN=your-token-here
MAX_MESSAGES=0
```

**2. Export in shell**:
```bash
export MEM_API_URL=http://localhost:14243
export MEM_AUTH_TOKEN=your-token-here
export MAX_MESSAGES=100
```

**3. Inline with command**:
```bash
MEM_API_URL=http://localhost:14243 uv run python -m mem_persist save
```

**Priority** (highest to lowest):
1. Existing environment variables (shell exports)
2. Variables from `.env` file
3. Default values

**Available variables**:
- `MEM_API_URL` - API endpoint (default: `http://localhost:14243`)
- `MEM_AUTH_TOKEN` - Bearer token (default: `helloworld`)
- `MAX_MESSAGES` - Message limit, 0=unlimited (default: `0`)

## Architecture

```
┌─────────────────┐      HTTP POST /threads       ┌──────────────────┐
│  Client Machine │ ───────────────────────────► │  MCP Server      │
│  (Laptop)       │      with JSON payload        │  (Remote)        │
│                 │                                │                  │
│  1. Read local  │                                │  4. Store in     │
│     session     │                                │     database     │
│  2. Convert to  │                                │                  │
│     API format  │                                │  5. Build graph  │
│  3. Send via    │                                │                  │
│     HTTP API    │                                │  6. Index for    │
│                 │                                │     search       │
└─────────────────┘                                └──────────────────┘
```

## Data Flow

1. **Discovery**: Find session directory using path encoding rules:
   - `/.` → `--` (hidden directories)
   - `/` → `-` (regular directories)
   - Example: `/home/user/.claude/skills` → `-home-user--claude-skills`
2. **Read**: Load most recent session JSON file
3. **Transform**: Convert to Nowledge Mem format:
   ```json
   {
     "thread_id": "project_20251109_142918",
     "title": "Claude Code Session - 2025-11-09",
     "messages": [
       {"role": "user", "content": "...", "timestamp": "..."},
       {"role": "assistant", "content": "...", "timestamp": "..."}
     ],
     "participants": ["user", "claude"],
     "source": "claude-code",
     "project": "jura-arh",
     "workspace": "/home/user/projects/jura-arh",
     "metadata": {...}
   }
   ```
4. **Send**: POST to `/threads` endpoint with Bearer token
5. **Verify**: Check HTTP 200/201 response

## Comparison with MCP Tool

| Feature | MCP `thread_persist` | This Skill |
|---------|---------------------|------------|
| **Location** | Server-side | Client-side |
| **Access** | Needs filesystem access | Uses HTTP API |
| **Works remotely** | ❌ No | ✅ Yes |
| **Network** | Same machine only | Any network |
| **Authentication** | MCP protocol | HTTP Bearer token |
| **Session format** | Direct file read | Converts to API format |

## Troubleshooting

Run diagnostics:
```bash
uv run python -m mem_persist diagnose
```

This checks:
- ✓ API connectivity
- ✓ Authentication
- ✓ Python version compatibility
- ✓ Session directory existence

### Common Issues

**"No session directory found"**
- Claude Code hasn't created session files yet
- Wrong project directory
- Session files in non-standard location

**"API connection failed"**
- Server not running
- Wrong API URL
- Network/firewall issues
- VPN/Tailscale not connected

**"Authentication failed"**
- Wrong token
- Token expired
- Server requires different auth method

## Development

### File Structure

```
mem-persist/
├── SKILL.md              # Skill metadata (for Claude)
├── README.md             # This file (documentation)
├── CLAUDE.md             # Instructions for Claude Code
├── pyproject.toml        # Python project config
└── mem_persist/          # Python package
    ├── __init__.py       # Package init
    ├── __main__.py       # Entry point for `python -m`
    ├── cli.py            # Click CLI commands
    ├── config.py         # Configuration management
    ├── session.py        # Session discovery & parsing
    ├── api.py            # HTTP API client
    └── diagnostics.py    # Diagnostic utilities
```

### Testing

```bash
# Test with debug output
uv run python -m mem_persist save --debug

# Test with custom config
MEM_API_URL=http://localhost:14243 \
MEM_AUTH_TOKEN=test \
uv run python -m mem_persist save --title "Test"

# Run diagnostics
uv run python -m mem_persist diagnose
```

### Extending

To support other AI coding tools (Cursor, Codex, etc.):

1. Update `find_session_directory()` in `session.py` with new path patterns
2. Add format-specific parsers in `parse_session_file()`
3. Update `source` field in API payload to identify the tool

All logic is now in Python modules, making it easier to test and extend.

## Best Practices

Following Claude Code Agent Skills optimization guidelines:

- ✅ **Pure Python**: No shell scripts, easier to maintain and test
- ✅ **Single command**: `uv run python -m mem_persist save` does everything
- ✅ **Progressive disclosure**: SKILL.md is concise, README has details
- ✅ **Environment-based config**: No hardcoded values
- ✅ **Diagnostic tooling**: Built-in `diagnose` command
- ✅ **Type-safe**: Modern Python with type hints

## License

Same as Nowledge Mem project.

## Related

- Issue: [nowledge-mem#7](https://github.com/nowledge-co/nowledge-mem/issues/7)
- API Docs: https://mem.nowledge.co/docs/api
- MCP Protocol: https://github.com/nowledge-co/nowledge-mem
