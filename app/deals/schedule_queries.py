"""Database queries used by the scheduled-deal worker."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Deal, ScheduledDealPost


def get_pending_schedules(db: Session) -> list[ScheduledDealPost]:
    """Return queued schedules whose deals have not been cancelled."""
    return db.scalars(
        select(ScheduledDealPost)
        .join(Deal, Deal.id == ScheduledDealPost.deal_id)
        .where(
            ScheduledDealPost.status.in_(["pending", "burst_pending"]),
            func.lower(func.trim(Deal.status)) != "cancelled",
        )
        .order_by(ScheduledDealPost.scheduled_at.asc())
    ).all()
