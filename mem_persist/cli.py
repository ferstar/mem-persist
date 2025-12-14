"""Command-line interface for mem-persist using Click"""

import logging
import sys

import click

from .api import APIClient, APIError
from .config import Config, ConfigError
from .diagnostics import Colors, print_info, run_diagnostics
from .session import (
    SessionNotFoundError,
    build_thread_request,
    find_latest_session_for_project,
    parse_session_file,
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Version - keep in sync with pyproject.toml
VERSION = "1.2.0"


@click.group()
@click.version_option(version=VERSION, prog_name="mem-persist")
def cli():
    """Save Claude Code or Codex CLI conversation threads to Nowledge Mem"""
    pass


@cli.command()
@click.option(
    "-t", "--title",
    help="Custom thread title (auto-generated if not provided)",
)
@click.option(
    "-p", "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=str),
    help="Project directory path (default: current directory)",
)
@click.option(
    "--source",
    type=click.Choice(["auto", "claude", "codex"], case_sensitive=False),
    help="Session source hint (override auto-detection)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode (show full tracebacks)",
)
def save(title: str | None, project_path: str | None, source: str | None, debug: bool):
    """Save current session to Nowledge Mem"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load config with session_source from CLI
        config = Config.from_env(
            project_path=project_path,
            session_source=source,
        )

        click.echo(f"{Colors.BLUE}[mem-persist]{Colors.RESET} Saving current session...\n")

        # Find session file from Claude Code or Codex CLI
        session_file, session_source = find_latest_session_for_project(
            config.project_path,
            config.session_source,
        )

        session_size = session_file.stat().st_size / 1024  # KB
        print_info(f"Project: {config.project_path.name}")
        print_info(f"Session: {session_file.name} ({session_size:.1f} KB)")
        print_info(f"Source: {session_source}")

        # Parse session - returns ParseResult with messages AND total_lines
        limit_msg = "no limit" if config.max_messages == 0 else f"max {config.max_messages}"
        click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} Parsing session ({limit_msg})...")

        parse_result = parse_session_file(session_file, config.max_messages)
        messages = parse_result.messages
        total_lines = parse_result.total_lines  # No need to re-read the file!

        print_info(f"Extracted {len(messages)} messages from {total_lines} lines")

        # Build request payload
        payload = build_thread_request(
            messages=messages,
            project_path=config.project_path,
            session_file=session_file,
            custom_title=title or "",
            total_lines=total_lines,
            source=session_source,
        )

        print_info(f"Thread ID: {payload['thread_id']}")
        print_info(f"Title: {payload['title'][:60]}")

        # Upload to API with connection pooling
        click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} Uploading to Nowledge Mem...")

        with APIClient(
            config.api_url,
            config.auth_token,
            timeout_health=config.timeout_health,
            timeout_request=config.timeout_request,
        ) as client:
            response = client.save_thread(payload)

        # Parse response
        thread_data = response.get("thread", {})

        click.echo(f"\n{Colors.GREEN}Thread saved successfully!{Colors.RESET}\n")
        print_info(f"Thread ID: {thread_data.get('thread_id', 'N/A')}")
        print_info(f"Server ID: {thread_data.get('id', 'N/A')}")
        print_info(f"Messages: {thread_data.get('message_count', len(messages))}")

        click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} Done! Conversation stored in Nowledge Mem.\n")

    except ConfigError as e:
        click.echo(f"\n{Colors.RED}Configuration Error:{Colors.RESET} {e}\n", err=True)
        click.echo("Set MEM_AUTH_TOKEN via environment variable or .env file.", err=True)
        sys.exit(1)

    except SessionNotFoundError as e:
        click.echo(f"\n{Colors.RED}Session Error:{Colors.RESET} {e}\n", err=True)
        sys.exit(1)

    except APIError as e:
        click.echo(f"\n{Colors.RED}API Error:{Colors.RESET} {e}\n", err=True)
        if hasattr(e, 'status_code') and e.status_code:
            click.echo(f"HTTP Status: {e.status_code}", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"\n{Colors.RED}Unexpected error:{Colors.RESET} {e}\n", err=True)
        if debug:
            raise
        sys.exit(1)


@cli.command()
@click.option(
    "-p", "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=str),
    help="Project directory path (default: current directory)",
)
@click.option(
    "--source",
    type=click.Choice(["auto", "claude", "codex"], case_sensitive=False),
    help="Session source hint (override auto-detection)",
)
def diagnose(project_path: str | None, source: str | None):
    """Run diagnostic checks"""
    try:
        config = Config.from_env(
            project_path=project_path,
            session_source=source,
        )
        success = run_diagnostics(config)
        sys.exit(0 if success else 1)
    except ConfigError as e:
        click.echo(f"\n{Colors.RED}Configuration Error:{Colors.RESET} {e}\n", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
