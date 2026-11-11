"""Link an existing agent profile to the configured Discord bot account."""
import argparse

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Agent, AgentProfile


def link_discord_bot(agent_name: str, discord_bot_id: str) -> None:
    db = SessionLocal()
    try:
        agent = db.scalar(select(Agent).where(Agent.name == agent_name))
        if agent is None:
            raise ValueError(f"Agent not found: {agent_name}")
        profile = db.scalar(
            select(AgentProfile).where(AgentProfile.agent_id == agent.id)
        )
        if profile is None:
            raise ValueError(f"Profile not found for: {agent_name}")
        profile.discord_bot_id = discord_bot_id
        db.commit()
        print(f"Linked {agent_name} to Discord bot {discord_bot_id}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_name")
    parser.add_argument("discord_bot_id")
    args = parser.parse_args()
    link_discord_bot(args.agent_name, args.discord_bot_id)


if __name__ == "__main__":
    main()
