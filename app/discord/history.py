from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, ConversationMessage


def save_message(
    db: Session,
    agent_id: int,
    channel_id: str,
    user_id: str,
    role: str,
    content: str,
) -> ConversationMessage:

    message = ConversationMessage(
        agent_id=agent_id,
        channel_id=channel_id,
        user_id=user_id,
        role=role,
        content=content,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def get_conversation_history(
    db: Session,
    agent_id: int,
    channel_id: str,
    limit: int = 10,
) -> list[dict[str, str]]:

    messages = db.scalars(
        select(ConversationMessage)
        .where(
            ConversationMessage.agent_id == agent_id,
            ConversationMessage.channel_id == channel_id,
        )
        .order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        )
        .limit(limit)
    ).all()

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]