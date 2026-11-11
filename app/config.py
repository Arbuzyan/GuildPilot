
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def get_env(name: str, default: str = "") -> str:
    """Read an environment variable and remove surrounding whitespace."""
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = field(
        default_factory=lambda: get_env("DATABASE_URL")
    )

    ANTHROPIC_API_KEY: str = field(
        default_factory=lambda: get_env("ANTHROPIC_API_KEY")
    )

    ANTHROPIC_MODEL: str = field(
        default_factory=lambda: get_env(
            "ANTHROPIC_MODEL",
            "claude-sonnet-4-6",
        )
    )

    ROSA_DISCORD_TOKEN: str = field(
        default_factory=lambda: get_env("ROSA_DISCORD_TOKEN")
    )

    ROSA_DISCORD_CHANNEL_ID: str = field(
        default_factory=lambda: get_env("ROSA_DISCORD_CHANNEL_ID")
    )

    DISCORD_GUILD_ID: str = field(
        default_factory=lambda: get_env("DISCORD_GUILD_ID")
    )

    LIVE_BOARD_URL: str = field(
        default_factory=lambda: get_env(
            "LIVE_BOARD_URL",
            "https://discord.com",
        )
    )


settings = Settings()
