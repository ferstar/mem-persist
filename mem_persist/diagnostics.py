"""Diagnostic utilities for troubleshooting"""

import sys

from .api import APIClient
from .config import Config
from .session import SessionNotFoundError, find_latest_session_for_project


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    RESET = "\033[0m"


def print_status(message: str, success: bool):
    """Print status message with color-coded symbol"""
    symbol = "+" if success else "x"
    color = Colors.GREEN if success else Colors.RED
    print(f"{color}[{symbol}]{Colors.RESET} {message}")


def print_info(message: str):
    """Print info message with blue indicator"""
    print(f"{Colors.BLUE}[i]{Colors.RESET} {message}")


def print_warning(message: str):
    """Print warning message with yellow indicator"""
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {message}")


def run_diagnostics(config: Config) -> bool:
    """Run diagnostic checks for mem-persist

    Checks:
    1. API connectivity (health endpoint)
    2. Authentication (authenticated endpoint)
    3. Project directory and session files
    4. Python version compatibility

    Args:
        config: Configuration object

    Returns:
        True if all checks pass, False otherwise
    """
    all_passed = True

    print(f"\n{Colors.BLUE}=== mem-persist Diagnostics ==={Colors.RESET}\n")

    # Create API client with connection pooling
    with APIClient(
        config.api_url,
        config.auth_token,
        timeout_health=config.timeout_health,
        timeout_request=config.timeout_request,
    ) as client:

        # 1. Check API connectivity
        print(f"Checking API connectivity: {config.api_url}")
        is_healthy, health_error = client.health_check()

        if is_healthy:
            print_status("API is reachable and healthy", True)
        else:
            print_status(f"API health check failed: {health_error}", False)
            all_passed = False

        # 2. Check authentication (ACTUALLY test auth, not just health again!)
        print("\nChecking authentication...")
        is_authenticated, auth_error = client.auth_check()

        if is_authenticated:
            print_status("Authentication successful", True)
            if auth_error:  # May have a warning message
                print_warning(auth_error)
        else:
            print_status(f"Authentication failed: {auth_error}", False)
            all_passed = False

    # 3. Check project and session directory
    print(f"\nChecking project: {config.project_path}")

    if config.project_path.exists():
        print_status("Project directory exists", True)
        print_info(f"Session source hint: {config.session_source}")

        try:
            session_file, session_source = find_latest_session_for_project(
                config.project_path,
                config.session_source,
            )
            print_status("Latest session file located", True)
            print_info(f"Source: {session_source}")
            print_info(f"Session file: {session_file}")

            # Show file stats
            try:
                stat = session_file.stat()
                size_kb = stat.st_size / 1024
                print_info(f"File size: {size_kb:.1f} KB")
            except OSError:
                pass

        except SessionNotFoundError as e:
            print_status("Session file not found", False)
            print_info(str(e))
            all_passed = False
    else:
        print_status("Project directory does not exist", False)
        all_passed = False

    # 4. Check Python version
    print("\nChecking Python environment...")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print_info(f"Python {py_version}")

    if sys.version_info >= (3, 10):
        print_status("Python version is compatible (3.10+)", True)
    else:
        print_status("Python version is too old (need 3.10+)", False)
        all_passed = False

    # 5. Show configuration summary
    print("\nConfiguration:")
    print_info(f"API URL: {config.api_url}")
    print_info(f"Auth token: {'*' * 8}...{config.auth_token[-4:] if len(config.auth_token) > 4 else '****'}")
    print_info(f"Max messages: {config.max_messages or 'unlimited'}")
    print_info(f"Health timeout: {config.timeout_health}s")
    print_info(f"Request timeout: {config.timeout_request}s")

    # Summary
    print(f"\n{Colors.BLUE}=== Summary ==={Colors.RESET}\n")
    if all_passed:
        print(f"{Colors.GREEN}[+] All checks passed!{Colors.RESET}")
        print("\nYou can now run: uv run python -m mem_persist save")
    else:
        print(f"{Colors.RED}[x] Some checks failed{Colors.RESET}")
        print("\nPlease fix the issues above before proceeding.")

    return all_passed
