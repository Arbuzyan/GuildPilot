from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, Deal


def import_deals(db: Session, file_path: str | Path) -> int:
    workbook = load_workbook(file_path, data_only=True)
    sheet = workbook["Deals"]

    imported = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        (
            date,
            agent_name,
            client,
            carrier,
            product,
            annual_premium,
            status,
            policy_number,
            data_type,
        ) = row

        # Ищем агента
        agent = db.scalar(
            select(Agent).where(Agent.name == agent_name)
        )

        # Если агента ещё нет — создаём
        if agent is None:
            agent = Agent(name=agent_name)
            db.add(agent)
            db.flush()

        # Проверяем, не импортировали ли уже эту сделку
        existing_deal = db.scalar(
            select(Deal).where(
                Deal.policy_number == policy_number
            )
        )

        if existing_deal:
            skipped += 1
            continue

        # Создаём сделку
        deal = Deal(
            date=date,
            agent_id=agent.id,
            client=client,
            carrier=carrier,
            product=product,
            annual_premium=annual_premium,
            status=status,
            policy_number=policy_number,
            data_type=data_type,
        )

        db.add(deal)
        imported += 1

    db.commit()

    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")

    return imported