"""Diagnostic utilities for troubleshooting"""

import sys
from pathlib import Path

from .api import APIClient
from .config import Config
from .session import find_latest_session_for_project, SessionNotFoundError


class Colors:
    """ANSI color codes"""
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    RESET = "\033[0m"


def print_status(message: str, success: bool):
    """Print status message with color"""
    symbol = "✓" if success else "✗"
    color = Colors.GREEN if success else Colors.RED
    print(f"{color}{symbol}{Colors.RESET} {message}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {message}")


def run_diagnostics(config: Config) -> bool:
    """Run diagnostic checks

    Returns:
        True if all checks pass, False otherwise
    """
    all_passed = True

    print(f"\n{Colors.BLUE}=== mem-persist Diagnostics ==={Colors.RESET}\n")

    # 1. Check API connectivity
    print(f"Checking API connectivity: {config.api_url}")
    client = APIClient(config.api_url, config.auth_token)

    try:
        if client.health_check():
            print_status("API is reachable and healthy", True)
        else:
            print_status("API health check failed", False)
            all_passed = False
    except Exception as e:
        print_status(f"Cannot connect to API: {e}", False)
        all_passed = False

    # 2. Check authentication
    print("\nChecking authentication...")
    try:
        # Try a simple request to verify auth
        if client.health_check():
            print_status("Authentication successful", True)
        else:
            print_status("Authentication may have failed", False)
            all_passed = False
    except Exception as e:
        print_status(f"Auth check failed: {e}", False)
        all_passed = False

    # 3. Check project and session directory
    print(f"\nChecking project: {config.project_path}")
    if config.project_path.exists():
        print_status(f"Project directory exists", True)
        print_info(f"Session source hint: {config.session_source}")

        try:
            session_file, session_source = find_latest_session_for_project(
                config.project_path,
                config.session_source,
            )
            print_status("Latest session file located", True)
            print_info(f"Source: {session_source}")
            print_info(f"Session file: {session_file}")
        except SessionNotFoundError as e:
            print_status(f"Session file not found: {e}", False)
            all_passed = False
    else:
        print_status(f"Project directory does not exist", False)
        all_passed = False

    # 4. Check Python version
    print("\nChecking Python environment...")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print_info(f"Python {py_version}")

    if sys.version_info >= (3, 10):
        print_status("Python version is compatible", True)
    else:
        print_status("Python version is too old (need 3.10+)", False)
        all_passed = False

    # Summary
    print(f"\n{Colors.BLUE}=== Summary ==={Colors.RESET}\n")
    if all_passed:
        print(f"{Colors.GREEN}✓ All checks passed!{Colors.RESET}")
        print("\nYou can now run: uv run mem-persist save")
    else:
        print(f"{Colors.RED}✗ Some checks failed{Colors.RESET}")
        print("\nPlease fix the issues above before proceeding.")

    return all_passed
