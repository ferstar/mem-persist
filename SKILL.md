---
name: mem-persist
description: Save Claude Code conversation threads to Nowledge Mem knowledge base. Auto-triggered when user requests to save/persist current session.
---

# Save Conversation to Nowledge Mem

Automatically save the current Claude Code conversation thread to Nowledge Mem knowledge base.

## When to Use

Trigger this skill when user says:
- "save current thread" / "保存当前thread"
- "save this session" / "保存这个会话"
- "persist conversation" / "持久化对话"
- "backup session" / "备份会话"
- Any similar request to save conversation history

## Usage

**Save current session** (when called from another project):
```bash
PROJECT_PATH=/path/to/actual/project uv run python -m mem_persist save
```

**With custom title**:
```bash
PROJECT_PATH=/path/to/actual/project uv run python -m mem_persist save --title "Your title here"
```

**Run diagnostics** (if issues occur):
```bash
PROJECT_PATH=/path/to/actual/project uv run python -m mem_persist diagnose
```

**Note for Claude Code**: When invoking this skill from another project, always set `PROJECT_PATH` environment variable to the actual project directory. Use the current working directory from `<env>` block.

## What Happens

1. 🔍 Auto-detects current project and session
2. 📖 Finds and parses latest session file
3. 🔄 Converts to API format
4. 📤 Uploads to Nowledge Mem server
5. ✅ Returns confirmation with thread details

## Configuration

Optional `.env` file (place in project root):
```bash
MEM_API_URL=http://your-server:14243
MEM_AUTH_TOKEN=your-token-here
MAX_MESSAGES=0  # 0 = unlimited
```

Or use environment variables - see [README.md](./README.md) for details.

## Expected Output

```
✅ Thread saved successfully!
🆔 Thread ID: project_20251110_065118
🔗 Server ID: 0a63f067-9e77-42e8-95b3-ea4a722543e8
📊 Messages: 36
```

## Notes

- Pure Python implementation (v1.0.0)
- Zero configuration needed (uses defaults)
- Supports unlimited messages by default
- Handles both English and Chinese content
- Requires `uv` for execution

For detailed documentation, see [README.md](./README.md).
