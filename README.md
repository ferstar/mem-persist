# ⚠️ 已弃用 / DEPRECATED

此仓库已归档。功能已合并到统一插件：

👉 **[nowledge-mem-plugins](https://github.com/ferstar/nowledge-mem-plugins)**

---

# mem-persist

Save Claude Code / Codex CLI 会话到 Nowledge Mem 服务器。

## Overview

解决远程 MCP 服务器无法访问本地会话文件的问题（参见 [nowledge-mem#7](https://github.com/nowledge-co/nowledge-mem/issues/7)）。

**支持的 CLI**:
- **Claude Code**: `~/.claude/projects/-<encoded>/<session>.jsonl`
- **Codex CLI**: `~/.codex/sessions/YYYY/MM/DD/*.jsonl`

自动探测会话来源，无需手动配置。

## Quick Start

```bash
# 保存当前会话
PROJECT_PATH=/path/to/project uv run python -m mem_persist save

# 自定义标题
PROJECT_PATH=/path/to/project uv run python -m mem_persist save --title "Feature X"

# 强制指定来源
PROJECT_PATH=/path/to/project uv run python -m mem_persist save --source codex

# 诊断
PROJECT_PATH=/path/to/project uv run python -m mem_persist diagnose
```

## Configuration

**环境变量** (通过 `.env` 或 shell export):

| 变量 | 必须 | 默认值 | 说明 |
|------|------|--------|------|
| `MEM_AUTH_TOKEN` | **是** | - | Bearer token |
| `MEM_API_URL` | 否 | `http://localhost:14243` | API 地址 |
| `PROJECT_PATH` | 否 | 当前目录 | 项目路径 |
| `MAX_MESSAGES` | 否 | `0` (无限) | 最大消息数 |
| `MEM_SESSION_SOURCE` | 否 | `auto` | `auto`/`claude`/`codex` |
| `MEM_TIMEOUT_HEALTH` | 否 | `5.0` | 健康检查超时(秒) |
| `MEM_TIMEOUT_REQUEST` | 否 | `30.0` | 请求超时(秒) |

**.env 示例**:
```bash
MEM_API_URL=http://your-server:14243
MEM_AUTH_TOKEN=your-token-here
```

## Architecture

```
┌─────────────────┐      HTTP POST /threads       ┌──────────────────┐
│  Client Machine │ ───────────────────────────► │  Remote Server   │
│                 │                               │                  │
│  1. Read local  │                               │  4. Store in DB  │
│     session     │                               │  5. Build graph  │
│  2. Convert fmt │                               │  6. Index search │
│  3. HTTP POST   │                               │                  │
└─────────────────┘                               └──────────────────┘
```

## Troubleshooting

```bash
uv run python -m mem_persist diagnose
```

**常见问题**:

| 错误 | 原因 |
|------|------|
| `Configuration Error: MEM_AUTH_TOKEN is required` | 未设置认证 token |
| `Session directory not found` | 项目没有会话文件，或路径错误 |
| `API connection failed` | 服务器未运行 / URL 错误 / 网络问题 |

## Development

```
mem-persist/
├── SKILL.md              # Skill 元数据
├── README.md             # 本文档
├── CLAUDE.md             # Claude Code 指南
├── pyproject.toml        # Python 配置
└── mem_persist/          # Python 包
    ├── cli.py            # CLI 入口
    ├── config.py         # 配置管理
    ├── session.py        # 会话发现与解析
    ├── api.py            # HTTP 客户端
    └── diagnostics.py    # 诊断工具
```

**扩展支持其他 CLI** (如 Cursor):
1. 在 `session.py` 添加新的会话发现逻辑
2. 添加格式解析器
3. 更新 `source` 字段
