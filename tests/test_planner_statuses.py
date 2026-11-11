"""Regression tests for schedule-state accounting and duplicate prevention."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Agent, Base, Deal, ScheduledDealPost
from app.deals import planner


class PlannerScheduleStatusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            self.agent = Agent(name="Planner Test Agent")
            db.add(self.agent)
            db.flush()
            self.deal = Deal(
                date=datetime(2026, 11, 9),
                agent_id=self.agent.id,
                client="Synthetic Client",
                carrier="Test Carrier",
                product="Test Product",
                annual_premium=100.0,
                term_months=12,
                status="Issued",
                policy_number="PLANNER-TEST-001",
                data_type="test",
            )
            db.add(self.deal)
            db.commit()
            self.agent_id = self.agent.id
            self.deal_id = self.deal.id

    def tearDown(self):
        self.engine.dispose()

    def add_schedule(self, status, schedule_id):
        with self.Session() as db:
            db.add(ScheduledDealPost(
                id=schedule_id,
                agent_id=self.agent_id,
                deal_id=self.deal_id,
                scheduled_at=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
                status=status,
            ))
            db.commit()

    def test_all_active_states_prevent_duplicate_planning(self):
        for status in ("pending", "burst_pending", "processing", "processing_burst"):
            with self.subTest(status=status):
                self.add_schedule(status, 100 + len(status))
                with self.Session() as db:
                    self.assertEqual(planner.get_available_deals(db, self.agent_id), [])

    def test_cancelled_schedule_does_not_block_replanning(self):
        self.add_schedule("cancelled", 201)
        with self.Session() as db:
            available = planner.get_available_deals(db, self.agent_id)
            self.assertEqual([deal.id for deal in available], [self.deal_id])

    def test_only_active_schedules_consume_daily_schedule_slots(self):
        for schedule_id, status in enumerate(
            ("pending", "burst_pending", "processing", "processing_burst", "completed", "cancelled", "failed"),
            start=300,
        ):
            self.add_schedule(status, schedule_id)

        start = datetime(2026, 11, 9, tzinfo=timezone.utc)
        end = datetime(2026, 11, 10, tzinfo=timezone.utc)
        with patch.object(planner, "local_day_bounds_utc", return_value=(start, end)):
            with self.Session() as db:
                self.assertEqual(
                    planner.get_today_scheduled_count(
                        db, self.agent_id, datetime(2026, 11, 9).date()
                    ),
                    4,
                )


if __name__ == "__main__":
    unittest.main()
