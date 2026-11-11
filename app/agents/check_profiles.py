from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Agent, AgentProfile


def main():
    db = SessionLocal()

    try:
        profiles = db.execute(
            select(Agent, AgentProfile)
            .join(AgentProfile)
            .order_by(Agent.name)
        )

        for agent, profile in profiles:
            print(
                f"{agent.name} | "
                f"profile_id={profile.id} | "
                f"discord_bot_id={profile.discord_bot_id} | "
                f"enabled={profile.enabled} | "
                f"daily_limit={profile.daily_limit}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()