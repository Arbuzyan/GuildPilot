from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Agent, ConversationMessage


def main():
    db = SessionLocal()

    try:
        messages = db.execute(
            select(
                Agent.name,
                ConversationMessage.channel_id,
                ConversationMessage.role,
                ConversationMessage.content,
                ConversationMessage.created_at,
            )
            .join(
                Agent,
                Agent.id == ConversationMessage.agent_id,
            )
            .order_by(
                ConversationMessage.created_at,
                ConversationMessage.id,
            )
        )

        for (
            agent_name,
            channel_id,
            role,
            content,
            created_at,
        ) in messages:

            print(
                f"[{created_at}] "
                f"{agent_name} | "
                f"channel={channel_id} | "
                f"{role}: {content}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()