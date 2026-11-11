from sqlalchemy import select

from app.agents.profiles import PILOT_AGENTS
from app.db.database import SessionLocal
from app.db.models import Agent, AgentProfile


def update_profiles() -> int:
    db = SessionLocal()
    updated = 0

    try:
        for agent_name, profile_data in PILOT_AGENTS.items():
            profile = db.scalar(
                select(AgentProfile)
                .join(Agent)
                .where(Agent.name == agent_name)
            )

            if profile is None:
                print(
                    f"Profile not found: {agent_name}"
                )
                continue

            profile.personality = profile_data["personality"]
            profile.communication_style = (
                profile_data["communication_style"]
            )
            profile.language = profile_data["language"]
            profile.system_prompt = profile_data["system_prompt"]
            profile.daily_limit = profile_data["daily_limit"]

            updated += 1

        db.commit()

        print(
            f"Profiles updated: {updated}"
        )

        return updated

    finally:
        db.close()


if __name__ == "__main__":
    update_profiles()