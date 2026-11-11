from app.core.time import local_day_bounds_utc, local_today, to_local

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Agent, ScheduledDealPost, Deal


def main():
    db = SessionLocal()

    try:
        print("=" * 80)
        print("TODAY'S SCHEDULE")
        print("=" * 80)

        today = local_today()
        start, end = local_day_bounds_utc(today)

        schedules = db.scalars(
            select(ScheduledDealPost)
            .join(Agent, ScheduledDealPost.agent_id == Agent.id)
            .join(Deal, ScheduledDealPost.deal_id == Deal.id)
            .where(
                ScheduledDealPost.scheduled_at >= start,
                ScheduledDealPost.scheduled_at < end,
            )
            .order_by(ScheduledDealPost.scheduled_at.asc())
        ).all()

        if not schedules:
            print("No schedules found for today.")
            return

        for schedule in schedules:
            print(
                f"ID={schedule.id} | "
                f"Agent={schedule.agent.name} | "
                f"Deal={schedule.deal_id} | "
                f"Time={to_local(schedule.scheduled_at).strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Status={schedule.status}"
            )

        print("=" * 80)
        print(f"TOTAL: {len(schedules)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()