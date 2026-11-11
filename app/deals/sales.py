from app.core.time import local_day_bounds_utc, local_today

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Agent, Deal, DealPost


def get_next_unposted_deal(
    db: Session,
    agent_name: str,
) -> Deal | None:

    deal = db.scalar(
        select(Deal)
        .join(Agent)
        .outerjoin(
            DealPost,
            DealPost.deal_id == Deal.id,
        )
        .where(
            Agent.name == agent_name,
            DealPost.id.is_(None),
            Deal.status == "Issued",
        )
        .order_by(
            Deal.date.asc(),
            Deal.id.asc(),
        )
    )

    return deal

def format_sales_post(deal: Deal) -> str:
    """Format a sale using only values stored on the deal record.

    This deliberately avoids inventing a channel, approval method, or product
    outcome that is not represented in the database.
    """
    return (
        f"Sale recorded for {deal.client}: "
        f"${deal.annual_premium:,.0f} annual premium; "
        f"carrier: {deal.carrier}; product: {deal.product}; "
        f"status: {deal.status}."
    )

def get_today_post_count(db: Session, agent_name: str) -> int:
    today = local_today()
    start_of_day, end_of_day = local_day_bounds_utc(today)

    count = db.scalar(
        select(func.count(DealPost.id))
        .join(Agent, DealPost.agent_id == Agent.id)
        .where(
            Agent.name == agent_name,
            DealPost.posted_at >= start_of_day,
            DealPost.posted_at < end_of_day,
        )
    )

    return count or 0

def can_post_deal(db: Session, agent_name: str, daily_limit: int) -> bool:
    today_count = get_today_post_count(db, agent_name)

    return today_count < daily_limit
