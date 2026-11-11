"""Regression tests for Discord sale card identity."""
import importlib.util
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Agent, Base, Deal

if importlib.util.find_spec("discord"):
    from app.discord.sales_commands import sale_embed


@unittest.skipUnless(importlib.util.find_spec("discord"), "discord.py is required for embed tests")
class SaleEmbedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_embed_displays_database_deal_id(self):
        with Session(self.engine) as db:
            agent = Agent(name="Test Agent")
            db.add(agent)
            db.flush()
            deal = Deal(
                id=42,
                date=datetime(2026, 11, 10),
                agent_id=agent.id,
                client="Synthetic Client",
                carrier="Test Carrier",
                product="FEX",
                annual_premium=1588,
                term_months=12,
                status="Pending",
                policy_number="TEST-EMBED-42",
                data_type="test",
            )
            db.add(deal)
            db.flush()

            embed = sale_embed(db, deal)

            self.assertEqual(embed.footer.text, "GuildPilot • Deal #42")
            self.assertIn("Test Agent", embed.description)
            fields = {field.name: field for field in embed.fields}
            self.assertTrue(fields["AP"].inline)
            self.assertFalse(fields["Carrier"].inline)
            self.assertFalse(fields["Product"].inline)


if __name__ == "__main__":
    unittest.main()
