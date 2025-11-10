"""Configuration management for mem-persist"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration for mem-persist"""

    api_url: str
    auth_token: str
    project_path: Path
    max_messages: int = 0  # 0 = unlimited

    @classmethod
    def from_env(cls, project_path: str | None = None, dotenv_path: str | None = None) -> "Config":
        """Load configuration from environment variables and .env file

        Args:
            project_path: Project directory path (default: current directory)
            dotenv_path: Path to .env file (default: searches in current dir and parents)

        Priority (highest to lowest):
            1. Existing environment variables
            2. Variables from .env file
            3. Default values

        Project path priority:
            1. project_path argument (CLI --project-path)
            2. PROJECT_PATH environment variable
            3. os.getcwd() (current directory)
        """
        # Load .env file (doesn't override existing env vars by default)
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        else:
            # Search for .env in current directory and parent directories
            load_dotenv(override=False)

        # Determine project path with proper priority
        resolved_project_path = (
            project_path  # CLI argument has highest priority
            or os.getenv("PROJECT_PATH")  # Then environment variable
            or os.getcwd()  # Finally fall back to current directory
        )

        return cls(
            api_url=os.getenv("MEM_API_URL", "http://localhost:14243"),
            auth_token=os.getenv("MEM_AUTH_TOKEN", "helloworld"),
            project_path=Path(resolved_project_path),
            max_messages=int(os.getenv("MAX_MESSAGES", "0")),
        )
