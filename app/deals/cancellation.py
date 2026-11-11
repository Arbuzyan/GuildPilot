"""Database operations for safely cancelling manually-created deals."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Deal, DealPost, ScheduledDealPost


MANUAL_SOURCE = "manual_discord"
ACTIVE_SCHEDULE_STATUSES = (
    "pending",
    "burst_pending",
    "processing",
    "processing_burst",
)


def cancel_manual_deal(
    db: Session,
    deal_id: int,
) -> tuple[Deal, DealPost | None]:
    """Mark a manual deal and its active schedules as cancelled.

    The caller owns the transaction and must commit or roll it back.
    A row lock serializes cancellation against scheduled publication on
    databases that support SELECT ... FOR UPDATE (including PostgreSQL).
    """
    deal = db.scalar(
        select(Deal)
        .where(Deal.id == deal_id)
        .with_for_update()
    )

    if deal is None:
        raise LookupError(f"Sale #{deal_id} not found.")

    if deal.data_type != MANUAL_SOURCE:
        raise ValueError("Imported sales cannot be undone from Discord.")

    if (deal.status or "").strip().lower() == "cancelled":
        raise ValueError(f"Sale #{deal_id} is already cancelled.")

    deal.status = "Cancelled"

    active_schedules = db.scalars(
        select(ScheduledDealPost)
        .where(
            ScheduledDealPost.deal_id == deal.id,
            ScheduledDealPost.status.in_(ACTIVE_SCHEDULE_STATUSES),
        )
        .with_for_update()
    ).all()

    for schedule in active_schedules:
        schedule.status = "cancelled"

    post = db.scalar(
        select(DealPost).where(DealPost.deal_id == deal.id)
    )

    db.flush()
    return deal, post
