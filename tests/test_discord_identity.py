"""Tests for stable Discord-member to agent identity mapping."""
import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentProfile, Base
from app.agents.discord_identity import get_or_create_discord_agent


class DiscordIdentityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_same_discord_user_resolves_to_same_agent(self):
        with Session(self.engine) as db:
            first = get_or_create_discord_agent(db, 123456789, "Arbuzer")
            db.commit()
            second = get_or_create_discord_agent(db, 123456789, "Arbuzer Updated")
            db.commit()
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.name, "Arbuzer Updated")
            self.assertEqual(second.discord_user_id, "123456789")
            self.assertIsNotNone(db.scalar(select(AgentProfile).where(AgentProfile.agent_id == second.id)))

    def test_name_collision_does_not_link_two_discord_users(self):
        with Session(self.engine) as db:
            first = get_or_create_discord_agent(db, 111111111, "Same Name")
            second = get_or_create_discord_agent(db, 222222222, "Same Name")
            db.commit()
            self.assertNotEqual(first.id, second.id)
            self.assertNotEqual(first.discord_user_id, second.discord_user_id)
            self.assertIn("22222222", second.name)


if __name__ == "__main__":
    unittest.main()
