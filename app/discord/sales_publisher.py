
import logging

import discord
from sqlalchemy import select

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    Agent,
    AgentProfile,
    Deal,
    DealPost,
)
from app.deals.sales import (
    get_next_unposted_deal,
    can_post_deal,
)
from app.deals.publication import publication_block_reason
from app.discord.sales_commands import sale_embed, sale_view


logger = logging.getLogger(__name__)

def get_channel_id() -> int:
    channel_id = settings.ROSA_DISCORD_CHANNEL_ID

    if not channel_id:
        raise RuntimeError(
            "ROSA_DISCORD_CHANNEL_ID is not set. "
            "Check your .env file."
        )

    try:
        return int(channel_id)
    except ValueError as exc:
        raise RuntimeError(
            "ROSA_DISCORD_CHANNEL_ID must be a valid integer."
        ) from exc


def create_deal_post(
    db,
    deal: Deal,
    channel_id: str,
    discord_message_id: str,
) -> DealPost:
    post = DealPost(
        deal_id=deal.id,
        agent_id=deal.agent_id,
        channel_id=channel_id,
        discord_message_id=discord_message_id,
    )

    db.add(post)
    db.flush()
    return post


async def publish_next_deal(
    client: discord.Client,
    agent_name: str,
) -> str:
    db = SessionLocal()

    try:
        deal = get_next_unposted_deal(db, agent_name)

        if deal is None:
            return "No unposted deal found."

        block_reason = publication_block_reason(deal)
        if block_reason:
            return block_reason

        channel_id = get_channel_id()
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        discord_message = await channel.send(
            embed=sale_embed(db, deal),
            view=sale_view(deal.id),
        )

        create_deal_post(
            db=db,
            deal=deal,
            channel_id=str(channel.id),
            discord_message_id=str(discord_message.id),
        )

        db.commit()

        return f"Deal {deal.id} posted successfully."

    except Exception:
        db.rollback()
        logger.exception("Manual deal publication failed")
        return "Publication failed. Check the application logs for details."

    finally:
        db.close()


async def publish_scheduled_deal(
    client: discord.Client,
    deal_id: int,
    bypass_daily_limit: bool = False,
) -> tuple[bool, str]:
    db = SessionLocal()

    try:
        # Serialize scheduled publication against /undo cancellation.
        # The row lock is held until the Discord send and DealPost commit finish.
        deal = db.scalar(
            select(Deal)
            .where(Deal.id == deal_id)
            .with_for_update()
        )

        if deal is None:
            return False, f"Deal {deal_id} not found."

        block_reason = publication_block_reason(deal)
        if block_reason:
            return False, block_reason

        agent = db.scalar(
            select(Agent).where(Agent.id == deal.agent_id)
        )

        if agent is None:
            return False, f"Agent for Deal {deal_id} not found."

        profile = db.scalar(
            select(AgentProfile).where(
                AgentProfile.agent_id == agent.id
            )
        )

        if profile is None:
            return False, f"Profile for agent {agent.name} not found."

        if not bypass_daily_limit and not can_post_deal(
            db=db,
            agent_name=agent.name,
            daily_limit=profile.daily_limit,
        ):
            return (
                False,
                f"LIMIT_REACHED: Daily message limit reached for "
                f"{agent.name} ({profile.daily_limit}).",
            )

        existing_post = db.scalar(
            select(DealPost).where(DealPost.deal_id == deal_id)
        )
        block_reason = publication_block_reason(deal, existing_post)
        if block_reason:
            return False, block_reason

        channel_id = get_channel_id()
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        discord_message = await channel.send(
            embed=sale_embed(db, deal),
            view=sale_view(deal.id),
        )

        create_deal_post(
            db=db,
            deal=deal,
            channel_id=str(channel.id),
            discord_message_id=str(discord_message.id),
        )

        db.commit()

        return True, f"Deal {deal_id} posted successfully."

    except Exception:
        db.rollback()
        logger.exception("Scheduled deal publication failed (deal_id=%s)", deal_id)
        return False, "Publication failed. Check the application logs for details."

    finally:
        db.close()
