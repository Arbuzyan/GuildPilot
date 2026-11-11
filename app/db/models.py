from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.time import utc_now


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    # Stable identity of the human Discord member who owns this sales profile.
    discord_user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )

    # Сделки агента
    deals: Mapped[list["Deal"]] = relationship(
        back_populates="agent",
    )

    # AI-профиль агента
    profile: Mapped["AgentProfile | None"] = relationship(
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
        unique=True,
    )

    personality: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    communication_style: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="English",
    )

    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    discord_bot_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    enabled: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    daily_limit: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="profile",
    )


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )

    client: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    carrier: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    product: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    annual_premium: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    term_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=12,
        server_default="12",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    policy_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    data_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="deals",
    )

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )

    channel_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    agent: Mapped["Agent"] = relationship()

class DealPost(Base):
    __tablename__ = "deal_posts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id"),
        nullable=False,
        unique=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )

    channel_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    discord_message_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    deal: Mapped["Deal"] = relationship()
    agent: Mapped["Agent"] = relationship()

class ScheduledDealPost(Base):
    __tablename__ = "scheduled_deal_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )

    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id"),
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    deal_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("deal_posts.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    agent: Mapped["Agent"] = relationship()
    deal: Mapped["Deal"] = relationship()
    deal_post: Mapped["DealPost | None"] = relationship()

class SaleEngagement(Base):
    __tablename__ = "sale_engagements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id"),
        nullable=False,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )

    discord_message_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    comment_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    engaged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    deal: Mapped["Deal"] = relationship()
    agent: Mapped["Agent"] = relationship()


class DealNote(Base):
    __tablename__ = "deal_notes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class AgentGoal(Base):
    __tablename__ = "agent_goals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
    )
