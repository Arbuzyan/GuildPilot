"""Integration tests for the GuildPilot soft-cancellation service.

Run from the project root with:
    python -m unittest discover -s tests -p "test_*.py" -v

These tests use an isolated in-memory SQLite database. They never connect to
or modify the configured PostgreSQL database.
"""

import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Agent, Base, Deal, DealNote, DealPost, ScheduledDealPost
from app.deals.cancellation import cancel_manual_deal


class SoftCancelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)

        self.agent = Agent(name="GuildPilot Test Agent")
        self.db.add(self.agent)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def make_deal(self, *, source: str = "manual_discord", status: str = "Pending") -> Deal:
        deal = Deal(
            date=datetime.now(),
            agent_id=self.agent.id,
            client="Synthetic Test Client",
            carrier="TEST",
            product="TEST",
            annual_premium=1.0,
            term_months=12,
            status=status,
            policy_number=f"TEST-{uuid4().hex}",
            data_type=source,
        )
        self.db.add(deal)
        self.db.commit()
        return deal

    def test_cancel_preserves_deal_note_post_and_cancels_active_schedules(self) -> None:
        deal = self.make_deal()
        note = DealNote(deal_id=deal.id, text="Synthetic audit note")
        post = DealPost(
            deal_id=deal.id,
            agent_id=self.agent.id,
            channel_id="111111111111111111",
            discord_message_id="222222222222222222",
        )
        pending = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=deal.id,
            scheduled_at=datetime.now() + timedelta(hours=1),
            status="pending",
        )
        burst = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=deal.id,
            scheduled_at=datetime.now() + timedelta(hours=2),
            status="burst_pending",
        )
        completed = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=deal.id,
            scheduled_at=datetime.now() - timedelta(hours=1),
            status="completed",
        )
        self.db.add_all([note, post, pending, burst, completed])
        self.db.commit()

        cancelled_deal, returned_post = cancel_manual_deal(self.db, deal.id)
        self.db.commit()

        self.assertEqual(cancelled_deal.status, "Cancelled")
        self.assertEqual(returned_post.id, post.id)
        self.assertIsNotNone(self.db.get(Deal, deal.id))
        self.assertIsNotNone(self.db.scalar(select(DealNote).where(DealNote.deal_id == deal.id)))
        self.assertIsNotNone(self.db.scalar(select(DealPost).where(DealPost.deal_id == deal.id)))
        statuses = {
            row.id: row.status
            for row in self.db.scalars(
                select(ScheduledDealPost).where(ScheduledDealPost.deal_id == deal.id)
            ).all()
        }
        self.assertEqual(statuses[pending.id], "cancelled")
        self.assertEqual(statuses[burst.id], "cancelled")
        self.assertEqual(statuses[completed.id], "completed")

    def test_imported_deal_is_rejected_without_changes(self) -> None:
        deal = self.make_deal(source="imported", status="Issued")

        with self.assertRaisesRegex(ValueError, "Imported sales"):
            cancel_manual_deal(self.db, deal.id)

        self.db.rollback()
        self.assertEqual(self.db.get(Deal, deal.id).status, "Issued")

    def test_already_cancelled_deal_is_rejected(self) -> None:
        deal = self.make_deal(status="Cancelled")

        with self.assertRaisesRegex(ValueError, "already cancelled"):
            cancel_manual_deal(self.db, deal.id)

        self.db.rollback()
        self.assertEqual(self.db.get(Deal, deal.id).status, "Cancelled")

    def test_missing_deal_is_rejected(self) -> None:
        with self.assertRaisesRegex(LookupError, "not found"):
            cancel_manual_deal(self.db, 999999)

    def test_cancellation_can_be_rolled_back(self) -> None:
        deal = self.make_deal()
        deal_id = deal.id
        cancel_manual_deal(self.db, deal_id)
        self.db.rollback()

        self.assertEqual(self.db.get(Deal, deal_id).status, "Pending")


if __name__ == "__main__":
    unittest.main()
