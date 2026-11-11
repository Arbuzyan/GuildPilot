"""Create the initial GuildPilot database schema.

Revision ID: aeb3e4d561c0
Revises:
Create Date: 2026-11-03 18:14:17.495414

This is the frozen pre-timezone baseline. Absolute timestamp columns are
intentionally created as timestamp without time zone so the following
c41d9e7a2b60 revision can apply the documented UTC/Moscow interpretation
consistently to both fresh installations and adopted legacy databases.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "aeb3e4d561c0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("communication_style", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("discord_bot_id", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("client", sa.String(length=100), nullable=False),
        sa.Column("carrier", sa.String(length=100), nullable=False),
        sa.Column("product", sa.String(length=20), nullable=False),
        sa.Column("annual_premium", sa.Float(), nullable=False),
        sa.Column("term_months", sa.Integer(), server_default="12", nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("policy_number", sa.String(length=50), nullable=False),
        sa.Column("data_type", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_number"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deal_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=100), nullable=False),
        sa.Column("discord_message_id", sa.String(length=100), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id"),
    )

    op.create_table(
        "scheduled_deal_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deal_post_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["deal_post_id"], ["deal_posts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sale_engagements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("discord_message_id", sa.String(length=100), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=True),
        sa.Column("engaged_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deal_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id"),
    )

    op.create_table(
        "agent_goals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("agent_goals")
    op.drop_table("deal_notes")
    op.drop_table("sale_engagements")
    op.drop_table("scheduled_deal_posts")
    op.drop_table("deal_posts")
    op.drop_table("conversation_messages")
    op.drop_table("deals")
    op.drop_table("agent_profiles")
    op.drop_table("agents")
