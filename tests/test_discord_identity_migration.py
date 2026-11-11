"""Regression test for the Discord identity schema migration."""
import importlib.util
import unittest
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


class DiscordIdentityMigrationTests(unittest.TestCase):
    def test_adds_nullable_unique_discord_user_id(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "d7f4a91c2e60_link_agents_to_discord_users.py"
        )
        spec = importlib.util.spec_from_file_location("discord_identity_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE agents (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE)"))
                connection.execute(text("INSERT INTO agents (id, name) VALUES (1, 'Legacy Agent')"))
                context = MigrationContext.configure(connection)
                with Operations.context(context):
                    migration.upgrade()
                columns = {column["name"]: column for column in inspect(connection).get_columns("agents")}
                self.assertIn("discord_user_id", columns)
                self.assertTrue(columns["discord_user_id"]["nullable"])
                self.assertEqual(connection.execute(text("SELECT name FROM agents WHERE id=1")).scalar(), "Legacy Agent")
                constraints = inspect(connection).get_unique_constraints("agents")
                self.assertTrue(any(item["name"] == "uq_agents_discord_user_id" for item in constraints))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
