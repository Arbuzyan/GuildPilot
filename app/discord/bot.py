"""Backward-compatible entry point for the GuildPilot Discord bot.

The canonical implementation lives in :mod:`app.discord.bot1`.
"""
from app.discord.bot1 import main


if __name__ == "__main__":
    main()
