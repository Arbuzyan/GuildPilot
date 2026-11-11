"""Publication eligibility tests using an isolated in-memory SQLite database.

Run from the project root:
    python -m unittest discover -s tests -p "test_*.py" -v

No configured PostgreSQL database or live Discord connection is used.
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Agent, Base, Deal, ScheduledDealPost
from app.deals.publication import publication_block_reason
from app.deals.schedule_queries import get_pending_schedules


class PublicationSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.agent = Agent(name="GuildPilot Publication Test Agent")
        self.db.add(self.agent)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def make_deal(self, status="Issued") -> Deal:
        deal = Deal(
            date=datetime.now(),
            agent_id=self.agent.id,
            client="Synthetic Publication Client",
            carrier="TEST",
            product="TEST",
            annual_premium=1.0,
            term_months=12,
            status=status,
            policy_number=f"TEST-PUBLISH-{uuid4().hex}",
            data_type="manual_discord",
        )
        self.db.add(deal)
        self.db.commit()
        return deal

    def test_cancelled_deal_is_rejected_before_publication(self):
        deal = self.make_deal(status="Cancelled")

        reason = publication_block_reason(deal)

        self.assertIsNotNone(reason)
        self.assertIn("cancelled", reason.lower())

    def test_normal_issued_deal_is_eligible_for_publication(self):
        deal = self.make_deal(status="Issued")

        reason = publication_block_reason(deal)

        self.assertIsNone(reason)

    def test_existing_post_blocks_duplicate_publication(self):
        deal = self.make_deal(status="Issued")
        existing_post = SimpleNamespace(id=123, deal_id=deal.id)

        reason = publication_block_reason(deal, existing_post)

        self.assertIsNotNone(reason)
        self.assertIn("already posted", reason.lower())

    def test_scheduler_excludes_cancelled_deals_and_cancelled_schedules(self):
        cancelled_deal = self.make_deal(status="Cancelled")
        active_deal = self.make_deal(status="Issued")
        cancelled_deal_schedule = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=cancelled_deal.id,
            scheduled_at=datetime.now() + timedelta(minutes=5),
            status="pending",
        )
        cancelled_status_schedule = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=active_deal.id,
            scheduled_at=datetime.now() + timedelta(minutes=10),
            status="cancelled",
        )
        valid_schedule = ScheduledDealPost(
            agent_id=self.agent.id,
            deal_id=active_deal.id,
            scheduled_at=datetime.now() + timedelta(minutes=15),
            status="pending",
        )
        self.db.add_all([
            cancelled_deal_schedule,
            cancelled_status_schedule,
            valid_schedule,
        ])
        self.db.commit()

        eligible = get_pending_schedules(self.db)

        self.assertEqual([row.id for row in eligible], [valid_schedule.id])


if __name__ == "__main__":
    unittest.main()
