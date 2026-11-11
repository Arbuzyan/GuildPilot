"""Link sales agents to their Discord member accounts.

Revision ID: d7f4a91c2e60
Revises: c41d9e7a2b60
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7f4a91c2e60"
down_revision: Union[str, Sequence[str], None] = "c41d9e7a2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode keeps this migration portable to SQLite-based migration tests
    # while emitting a normal ALTER TABLE on PostgreSQL.
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(sa.Column("discord_user_id", sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint("uq_agents_discord_user_id", ["discord_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("agents") as batch_op:
        batch_op.drop_constraint("uq_agents_discord_user_id", type_="unique")
        batch_op.drop_column("discord_user_id")
