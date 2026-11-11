"""Fresh-install bootstrap creates agent records and is safe to rerun."""
import unittest

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.db.models import Agent, AgentProfile, Base
from app.agents.profiles import PILOT_AGENTS, create_pilot_profiles


class ProfileBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_bootstrap_creates_agents_profiles_and_is_idempotent(self):
        with self.Session() as db:
            created = create_pilot_profiles(db)
            self.assertEqual(created, len(PILOT_AGENTS))
            self.assertEqual(
                db.scalar(select(func.count(Agent.id))),
                len(PILOT_AGENTS),
            )
            self.assertEqual(
                db.scalar(select(func.count(AgentProfile.id))),
                len(PILOT_AGENTS),
            )

            self.assertEqual(create_pilot_profiles(db), 0)
            self.assertEqual(
                db.scalar(select(func.count(AgentProfile.id))),
                len(PILOT_AGENTS),
            )


if __name__ == "__main__":
    unittest.main()
