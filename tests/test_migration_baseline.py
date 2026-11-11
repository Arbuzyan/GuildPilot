"""Structural regression test for the initial Alembic schema."""
import importlib.util
import unittest
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from app.db.models import Base


class InitialMigrationSchemaTests(unittest.TestCase):
    def test_baseline_creates_all_orm_tables_and_columns(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "aeb3e4d561c0_initial_database_schema.py"
        )
        spec = importlib.util.spec_from_file_location(
            "guildpilot_initial_migration", migration_path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                context = MigrationContext.configure(connection)
                with Operations.context(context):
                    migration.upgrade()

                inspector = inspect(connection)
                self.assertEqual(
                    set(inspector.get_table_names()),
                    set(Base.metadata.tables),
                )

                for table_name, model_table in Base.metadata.tables.items():
                    actual_columns = {
                        column["name"]
                        for column in inspector.get_columns(table_name)
                    }
                    expected_columns = set(model_table.columns.keys())
                    # discord_user_id is introduced by the follow-up migration,
                    # not by the frozen initial baseline.
                    if table_name == "agents":
                        expected_columns.discard("discord_user_id")
                    self.assertEqual(
                        actual_columns,
                        expected_columns,
                        msg=f"Column mismatch in {table_name}",
                    )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
