from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Deal, DealPost


def main():
    db = SessionLocal()

    try:
        posts = db.scalars(
            select(DealPost)
            .join(Deal, DealPost.deal_id == Deal.id)
            .where(
                DealPost.discord_message_id.is_not(None)
            )
            .order_by(DealPost.posted_at.asc())
        ).all()

        print("=" * 90)
        print("DEAL POSTS")
        print("=" * 90)

        for post in posts:
            print(
                f"Deal={post.deal_id} | "
                f"Agent={post.agent.name} | "
                f"Channel={post.channel_id} | "
                f"Message={post.discord_message_id} | "
                f"Posted={post.posted_at}"
            )

        print("=" * 90)
        print(f"TOTAL: {len(posts)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()