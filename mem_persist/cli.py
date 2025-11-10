"""Command-line interface for mem-persist using Click"""

import sys

import click

from .api import APIClient, APIError
from .config import Config
from .diagnostics import Colors, print_info, run_diagnostics
from .session import (
    SessionNotFoundError,
    build_thread_request,
    find_latest_session,
    find_session_directory,
    parse_session_file,
)


@click.group()
@click.version_option(version="2.0.0", prog_name="mem-persist")
def cli():
    """Save Claude Code conversation threads to Nowledge Mem"""
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
    "--debug",
    is_flag=True,
    help="Enable debug mode (show full tracebacks)",
)
def save(title, project_path, debug):
    """Save current session to Nowledge Mem"""
    try:
        # Load config
        config = Config.from_env(project_path)

        click.echo(f"{Colors.BLUE}[mem-persist]{Colors.RESET} 🚀 Saving current session...\n")

        # Find session directory and file
        session_dir = find_session_directory(config.project_path)
        session_file = find_latest_session(session_dir)

        session_size = session_file.stat().st_size / 1024  # KB
        print_info(f"Project: {config.project_path.name}")
        print_info(f"Session: {session_file.name} ({session_size:.1f} KB)")

        # Parse session
        if config.max_messages == 0:
            click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} 🔄 Parsing session (no limit)...")
        else:
            click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} 🔄 Parsing session (max {config.max_messages} messages)...")

        messages = parse_session_file(session_file, config.max_messages)

        # Count lines for metadata
        with session_file.open("r") as f:
            total_lines = sum(1 for _ in f)

        print_info(f"Extracted {len(messages)} messages from {total_lines} lines")

        # Build request payload
        payload = build_thread_request(
            messages=messages,
            project_path=config.project_path,
            session_file=session_file,
            custom_title=title or "",
            total_lines=total_lines,
        )

        print_info(f"Thread ID: {payload['thread_id']}")
        print_info(f"Title: {payload['title'][:60]}")

        # Upload to API
        click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} 📤 Uploading to Nowledge Mem...")

        client = APIClient(config.api_url, config.auth_token)
        response = client.save_thread(payload)

        # Parse response
        thread_data = response.get("thread", {})

        click.echo(f"\n{Colors.GREEN}✅ Thread saved successfully!{Colors.RESET}\n")
        print_info(f"🆔 Thread ID: {thread_data.get('thread_id', 'N/A')}")
        print_info(f"🔗 Server ID: {thread_data.get('id', 'N/A')}")
        print_info(f"📊 Messages: {thread_data.get('message_count', 'N/A')}")

        click.echo(f"\n{Colors.BLUE}[mem-persist]{Colors.RESET} ✨ Done! Conversation stored in Nowledge Mem.\n")

    except SessionNotFoundError as e:
        click.echo(f"\n{Colors.RED}✗ Error:{Colors.RESET} {e}\n", err=True)
        sys.exit(1)

    except APIError as e:
        click.echo(f"\n{Colors.RED}✗ API Error:{Colors.RESET} {e}\n", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"\n{Colors.RED}✗ Unexpected error:{Colors.RESET} {e}\n", err=True)
        if debug:
            raise
        sys.exit(1)


@cli.command()
@click.option(
    "-p", "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=str),
    help="Project directory path (default: current directory)",
)
def diagnose(project_path):
    """Run diagnostic checks"""
    config = Config.from_env(project_path)
    success = run_diagnostics(config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    cli()
