# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2025-11-10

### Fixed
- **Cross-project invocation bug**: When invoked from another project (e.g., as a Claude Code skill), the tool now correctly identifies the calling project instead of defaulting to the skill's own directory.

### Added
- Support for `PROJECT_PATH` environment variable to explicitly specify the project directory.
- Priority system for project path resolution:
  1. CLI `--project-path` argument (highest priority)
  2. `PROJECT_PATH` environment variable
  3. Current working directory (fallback)

### Changed
- Updated documentation in SKILL.md, CLAUDE.md, and README.md to reflect the new invocation pattern.
- Enhanced `Config.from_env()` to check `PROJECT_PATH` environment variable before falling back to `os.getcwd()`.

### Testing
- Added unit tests (`test_project_path.py`) to verify priority system.
- Added integration tests (`test_integration.py`) to validate cross-project invocation scenarios.

## [1.0.0] - 2025-11-10

### Added
- Initial release with pure Python implementation using Click CLI framework.
- `save` command: Save current session to Nowledge Mem.
- `diagnose` command: Run diagnostic checks.
- Environment-based configuration with `.env` file support.
- Type hints throughout the codebase.
- Custom exceptions: `SessionNotFoundError`, `APIError`.
- Support for Claude Code CLI session format.
- HTTP API integration with Nowledge Mem.

