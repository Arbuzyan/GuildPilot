"""Resolve Discord members to stable GuildPilot sales-agent records."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentProfile


def get_or_create_discord_agent(db: Session, user_id: int | str, display_name: str) -> Agent:
    """Return the agent linked to a Discord user, creating a neutral profile if needed."""
    discord_id = str(user_id)
    clean_name = (display_name or "Discord Member").strip()[:100] or "Discord Member"

    agent = db.scalar(select(Agent).where(Agent.discord_user_id == discord_id))
    if agent is None:
        # Agent.name is globally unique; make collisions deterministic without
        # exposing the numeric Discord ID in the visible display name normally.
        existing = db.scalar(select(Agent).where(Agent.name == clean_name))
        if existing is not None:
            suffix = f" ({discord_id[-8:]})"
            clean_name = f"{clean_name[:100-len(suffix)]}{suffix}"
        agent = Agent(name=clean_name, discord_user_id=discord_id)
        db.add(agent)
        db.flush()
    elif agent.name != clean_name:
        name_owner = db.scalar(select(Agent).where(Agent.name == clean_name, Agent.id != agent.id))
        if name_owner is None:
            agent.name = clean_name

    if agent.profile is None:
        db.add(AgentProfile(
            agent_id=agent.id,
            personality="Professional, helpful and factual.",
            communication_style="Clear, concise and respectful.",
            language="English",
            system_prompt=(
                f"You are the GuildPilot assistant for sales agent {agent.name}. "
                "Be helpful, concise, and factual. Never invent customer or sales data. "
                "Use only verified information supplied by the application."
            ),
            daily_limit=4,
        ))
        db.flush()

    return agent
