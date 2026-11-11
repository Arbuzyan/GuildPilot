from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.db.models import Agent, Deal


def main():
    db = SessionLocal()

    try:
        # Общее количество сделок
        total_deals = db.scalar(
            select(func.count(Deal.id))
        )

        print(f"Total deals: {total_deals}")

        # Количество агентов
        total_agents = db.scalar(
            select(func.count(Agent.id))
        )

        print(f"Total agents: {total_agents}")

        # Агенты и количество сделок
        print("\nAgents:")

        agents = db.execute(
            select(
                Agent.name,
                func.count(Deal.id),
            )
            .join(Deal)
            .group_by(Agent.id)
            .order_by(Agent.name)
        )

        for agent_name, deal_count in agents:
            print(f"{agent_name}: {deal_count}")

        # Продукты
        print("\nProducts:")

        products = db.execute(
            select(
                Deal.product,
                func.count(Deal.id),
            )
            .group_by(Deal.product)
        )

        for product, count in products:
            print(f"{product}: {count}")

    finally:
        db.close()


if __name__ == "__main__":
    main()