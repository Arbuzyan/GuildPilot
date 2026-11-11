from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, Deal


def get_latest_deal(
    db: Session,
    agent_name: str,
) -> Deal | None:

    deal = db.scalar(
        select(Deal)
        .join(Agent)
        .where(
            Agent.name == agent_name
        )
        .order_by(
            Deal.date.desc(),
            Deal.id.desc(),
        )
    )

    return deal

def format_deal_for_ai(deal: Deal) -> str:
    return (
        "Verified deal data:\n"
        f"Agent: {deal.agent.name}\n"
        f"Date: {deal.date.date()}\n"
        f"Client: {deal.client}\n"
        f"Carrier: {deal.carrier}\n"
        f"Product: {deal.product}\n"
        f"Annual Premium: ${deal.annual_premium:.2f}\n"
        f"Status: {deal.status}\n"
        f"Policy Number: {deal.policy_number}\n"
        f"Data Type: {deal.data_type}"
    )