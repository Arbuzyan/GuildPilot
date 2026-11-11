"""Convert absolute timestamps to timezone-aware PostgreSQL columns.

Revision ID: c41d9e7a2b60
Revises: aeb3e4d561c0

Legacy naive created_at/updated_at/posted_at/engaged_at values are interpreted
as UTC. Legacy scheduled_at values are interpreted as Europe/Moscow only when
the rows exactly match the audited historical set. A fresh installation has
no schedule rows and can safely convert the empty column without that guard.
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41d9e7a2b60"
down_revision: Union[str, Sequence[str], None] = "aeb3e4d561c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXPECTED_SCHEDULES = {
    73: datetime(2026, 10, 5, 6, 1, 39, 61650),
    74: datetime(2026, 10, 5, 6, 27, 47, 763559),
    75: datetime(2026, 10, 5, 6, 49, 36, 9417),
}

UTC_COLUMNS = (
    ("conversation_messages", "created_at"),
    ("deal_notes", "updated_at"),
    ("deal_posts", "posted_at"),
    ("sale_engagements", "engaged_at"),
    ("scheduled_deal_posts", "created_at"),
)
SCHEDULE_COLUMN = ("scheduled_deal_posts", "scheduled_at")


def _column_is_timezone_aware(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    if column_name not in columns:
        raise RuntimeError(
            f"Required column {table_name}.{column_name} is missing. "
            "Check the baseline migration or the legacy database schema."
        )
    return bool(getattr(columns[column_name]["type"], "timezone", False))


def _verify_historical_schedule_rows_if_present() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, scheduled_at FROM scheduled_deal_posts ORDER BY id")
    ).all()
    if not rows:
        return

    actual = {int(row.id): row.scheduled_at for row in rows}
    if actual != EXPECTED_SCHEDULES:
        raise RuntimeError(
            "Refusing to convert scheduled_deal_posts.scheduled_at: the existing "
            "rows do not match the audited historical set (IDs 73, 74, 75 and "
            "their exact naive timestamps). Audit every value and define an "
            "explicit timezone policy before retrying."
        )


def _convert_column(table_name: str, column_name: str, source_timezone: str) -> None:
    if _column_is_timezone_aware(table_name, column_name):
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using=f'"{column_name}" AT TIME ZONE \'{source_timezone}\'',
    )


def upgrade() -> None:
    # Validate required schema before issuing any ALTER statements.
    inspector = sa.inspect(op.get_bind())
    required_tables = {table for table, _ in (*UTC_COLUMNS, SCHEDULE_COLUMN)}
    missing = sorted(required_tables.difference(inspector.get_table_names()))
    if missing:
        raise RuntimeError(
            "Required tables are missing before timezone migration: "
            + ", ".join(missing)
            + ". The initial baseline migration must create the full schema."
        )

    if not _column_is_timezone_aware(*SCHEDULE_COLUMN):
        _verify_historical_schedule_rows_if_present()

    for table_name, column_name in UTC_COLUMNS:
        _convert_column(table_name, column_name, "UTC")

    _convert_column(*SCHEDULE_COLUMN, "Europe/Moscow")


def downgrade() -> None:
    # Revert only columns currently marked timezone-aware. The baseline schema
    # is naive, so downgrading to base restores its exact column types.
    columns = [*UTC_COLUMNS, SCHEDULE_COLUMN]
    for table_name, column_name in reversed(columns):
        if not _column_is_timezone_aware(table_name, column_name):
            continue
        timezone = "Europe/Moscow" if (table_name, column_name) == SCHEDULE_COLUMN else "UTC"
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(timezone=False),
            existing_nullable=False,
            postgresql_using=f'"{column_name}" AT TIME ZONE \'{timezone}\'',
        )
