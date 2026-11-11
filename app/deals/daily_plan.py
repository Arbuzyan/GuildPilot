from datetime import date

from app.core.time import local_today

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentProfile
from app.deals.planner import create_daily_plan


PILOT_AGENTS = [
    "Rosa Delgado",
    "Victor Lindqvist",
    "Devon Marsh",
    "Talia Brennan",
    "Sienna Boone",
]


def create_daily_plans(
    db: Session,
    target_date: date | None = None,
) -> dict[str, int]:
    """
    Создаёт дневные планы только для пилотных агентов.

    Возвращает:
        {
            "Rosa Delgado": 2,
            "Victor Lindqvist": 2,
            ...
        }
    """

    if target_date is None:
        target_date = local_today()

    result: dict[str, int] = {}

    for agent_name in PILOT_AGENTS:
        agent = db.scalar(
            select(Agent)
            .where(Agent.name == agent_name)
        )

        if agent is None:
            print(f"[PLAN] Agent not found: {agent_name}")
            result[agent_name] = 0
            continue

        profile = db.scalar(
            select(AgentProfile)
            .where(AgentProfile.agent_id == agent.id)
        )

        if profile is None:
            print(f"[PLAN] Profile not found: {agent_name}")
            result[agent_name] = 0
            continue

        posts = create_daily_plan(
            db=db,
            agent_name=agent_name,
            target_date=target_date,
        )

        result[agent_name] = len(posts)

    return result