from datetime import date, datetime, time, timedelta
import random

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.time import local_day_bounds_utc, local_now, local_today, to_utc
from app.db.models import (
    Agent,
    AgentProfile,
    Deal,
    DealPost,
    ScheduledDealPost,
)


def get_today_scheduled_count(
    db: Session,
    agent_id: int,
    target_date=None,
) -> int:
    if target_date is None:
        target_date = local_today()

    start, end = local_day_bounds_utc(target_date)

    return len(
        db.scalars(
            select(ScheduledDealPost)
            .where(
                ScheduledDealPost.agent_id == agent_id,
                ScheduledDealPost.scheduled_at >= start,
                ScheduledDealPost.scheduled_at < end,
                ScheduledDealPost.status.in_(
                    ["pending", "burst_pending", "processing", "processing_burst"]
                ),
            )
        ).all()
    )


def get_today_posted_count(
    db: Session,
    agent_id: int,
    target_date=None,
) -> int:
    if target_date is None:
        target_date = local_today()

    start, end = local_day_bounds_utc(target_date)

    return len(
        db.scalars(
            select(DealPost)
            .where(
                DealPost.agent_id == agent_id,
                DealPost.posted_at >= start,
                DealPost.posted_at < end,
            )
        ).all()
    )


def get_available_deals(
    db: Session,
    agent_id: int,
) -> list[Deal]:
    posted_deal_ids = select(DealPost.deal_id)

    scheduled_deal_ids = select(ScheduledDealPost.deal_id).where(
        ScheduledDealPost.status.in_(
            ["pending", "burst_pending", "processing", "processing_burst"]
        )
    )

    return list(
        db.scalars(
            select(Deal)
            .where(
                Deal.agent_id == agent_id,
                Deal.status == "Issued",
                ~Deal.id.in_(posted_deal_ids),
                ~Deal.id.in_(scheduled_deal_ids),
            )
            .order_by(Deal.date.asc(), Deal.id.asc())
        ).all()
    )


def calculate_schedule_times(
    count: int,
    target_date=None,
    start_hour: int = 10,
    end_hour: int = 20,
) -> list[datetime]:
    if target_date is None:
        target_date = local_today()

    if count <= 0:
        return []

    start_minutes = start_hour * 60
    end_minutes = end_hour * 60

    # Если планируем на сегодня,
    # не создаём события в прошлом.
    if target_date == local_today():
        now = local_now()
        current_minutes = now.hour * 60 + now.minute + 5
        start_minutes = max(start_minutes, current_minutes)

    # Если рабочее окно уже закончилось,
    # сегодня больше ничего не планируем.
    if start_minutes > end_minutes:
        return []

    available_minutes = end_minutes - start_minutes + 1

    if count > available_minutes:
        count = available_minutes

    if count == 1:
        minute = random.randint(
            start_minutes,
            end_minutes,
        )

        return [
            to_utc(datetime.combine(
                target_date,
                time(minute // 60, minute % 60),
                tzinfo=local_now().tzinfo,
            ))
        ]

    selected_minutes = sorted(
        random.sample(
            range(start_minutes, end_minutes + 1),
            count,
        )
    )

    return [
        to_utc(datetime.combine(
            target_date,
            time(minute // 60, minute % 60),
            tzinfo=local_now().tzinfo,
        ))
        for minute in selected_minutes
    ]


def create_daily_plan(
    db: Session,
    agent_name: str,
    target_date=None,
) -> list[ScheduledDealPost]:

    if target_date is None:
        target_date = local_today()

    agent = db.scalar(
        select(Agent).where(Agent.name == agent_name)
    )

    if agent is None:
        raise ValueError(f"Agent not found: {agent_name}")

    profile = db.scalar(
    select(AgentProfile).where(
        AgentProfile.agent_id == agent.id
    )
)

    if profile is None:
        raise ValueError(
            f"Profile not found: {agent_name}"
        )

    daily_limit = profile.daily_limit

    scheduled_count = get_today_scheduled_count(
        db,
        agent.id,
        target_date,
    )

    posted_count = get_today_posted_count(
        db,
        agent.id,
        target_date,
    )

    remaining_slots = daily_limit - scheduled_count - posted_count

    if remaining_slots <= 0:
        return []

    available_deals = get_available_deals(
        db,
        agent.id,
    )

    if not available_deals:
        return []

    count = min(
        remaining_slots,
        2,
        len(available_deals),
    )

    selected_deals = available_deals[:count]

    schedule_times = calculate_schedule_times(
        count=count,
        target_date=target_date,
    )

    created_posts = []

    for deal, scheduled_at in zip(
        selected_deals,
        schedule_times,
    ):
        scheduled_post = ScheduledDealPost(
            agent_id=agent.id,
            deal_id=deal.id,
            scheduled_at=scheduled_at,
            status="pending",
        )

        db.add(scheduled_post)
        created_posts.append(scheduled_post)

    db.commit()

    for post in created_posts:
        db.refresh(post)

    return created_posts