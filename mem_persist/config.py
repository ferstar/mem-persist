"""Configuration management for mem-persist"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Constants - no more magic numbers
DEFAULT_API_URL = "http://localhost:14243"
DEFAULT_TIMEOUT_HEALTH = 5.0
DEFAULT_TIMEOUT_REQUEST = 30.0
MIN_CONTENT_LENGTH = 5  # Minimum meaningful message length
MAX_CONTENT_LENGTH = 15000  # Truncate long messages
VALID_SESSION_SOURCES = frozenset({"auto", "claude", "codex"})


class ConfigError(Exception):
    """Raised when configuration is invalid"""
    pass


@dataclass
class Config:
    """Configuration for mem-persist

    Attributes:
        api_url: API endpoint URL
        auth_token: Bearer token for authentication (required, no default)
        project_path: Project directory path
        max_messages: Maximum messages to extract (0 = unlimited)
        session_source: Session source hint (auto/claude/codex)
        timeout_health: Timeout for health check requests
        timeout_request: Timeout for API requests
    """

    api_url: str
    auth_token: str
    project_path: Path
    max_messages: int = 0
    session_source: str = "auto"
    timeout_health: float = field(default=DEFAULT_TIMEOUT_HEALTH)
    timeout_request: float = field(default=DEFAULT_TIMEOUT_REQUEST)

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate auth_token
        if not self.auth_token or self.auth_token.strip() == "":
            raise ConfigError(
                "MEM_AUTH_TOKEN is required. "
                "Set it via environment variable or .env file."
            )

        # Validate max_messages
        if self.max_messages < 0:
            logger.warning(
                f"Invalid MAX_MESSAGES={self.max_messages}, using 0 (unlimited)"
            )
            object.__setattr__(self, 'max_messages', 0)

        # Validate session_source
        if self.session_source not in VALID_SESSION_SOURCES:
            logger.warning(
                f"Invalid session_source={self.session_source}, using 'auto'"
            )
            object.__setattr__(self, 'session_source', 'auto')

        # Validate timeouts
        if self.timeout_health <= 0:
            object.__setattr__(self, 'timeout_health', DEFAULT_TIMEOUT_HEALTH)
        if self.timeout_request <= 0:
            object.__setattr__(self, 'timeout_request', DEFAULT_TIMEOUT_REQUEST)

    @classmethod
    def from_env(
        cls,
        project_path: str | None = None,
        dotenv_path: str | None = None,
        session_source: str | None = None,
    ) -> "Config":
        """Load configuration from environment variables and .env file

        Args:
            project_path: Project directory path (default: current directory)
            dotenv_path: Path to .env file (default: searches in current dir and parents)
            session_source: Override session source (from CLI)

        Priority (highest to lowest):
            1. Function arguments (from CLI)
            2. Existing environment variables
            3. Variables from .env file

        Raises:
            ConfigError: If required configuration is missing or invalid
        """
        # Load .env file (doesn't override existing env vars)
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        else:
            load_dotenv(override=False)

        # Determine project path
        resolved_project_path = (
            project_path
            or os.getenv("PROJECT_PATH")
            or os.getcwd()
        )

        # Determine session source with CLI override
        resolved_session_source = (
            session_source
            or os.getenv("MEM_SESSION_SOURCE", "auto").strip().lower()
            or "auto"
        )

        # Parse max_messages safely
        try:
            max_messages = int(os.getenv("MAX_MESSAGES", "0"))
        except ValueError:
            logger.warning("Invalid MAX_MESSAGES value, using 0")
            max_messages = 0

        # Get auth token - NO DEFAULT VALUE
        auth_token = os.getenv("MEM_AUTH_TOKEN", "").strip()

        return cls(
            api_url=os.getenv("MEM_API_URL", DEFAULT_API_URL),
            auth_token=auth_token,
            project_path=Path(resolved_project_path),
            max_messages=max_messages,
            session_source=resolved_session_source,
            timeout_health=float(os.getenv("MEM_TIMEOUT_HEALTH", DEFAULT_TIMEOUT_HEALTH)),
            timeout_request=float(os.getenv("MEM_TIMEOUT_REQUEST", DEFAULT_TIMEOUT_REQUEST)),
        )
