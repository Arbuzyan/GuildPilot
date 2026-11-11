import logging
import os
import uuid
from datetime import datetime, timedelta

from typing import Optional

from app.config import settings
from app.core.time import local_now, local_today, utc_now

import discord
from discord import app_commands
from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.deals.cancellation import cancel_manual_deal
from app.agents.discord_identity import get_or_create_discord_agent
from app.db.models import (
    Agent,
    AgentGoal,
    Deal,
    DealNote,
    DealPost,
    ScheduledDealPost,
)


MANUAL_SOURCE = "manual_discord"
logger = logging.getLogger(__name__)



def money(value: float) -> str:
    return f"${value:,.0f}"


def progress_bar(value: float, goal: float, width: int = 10) -> str:
    if goal <= 0:
        return "░" * width
    ratio = max(0.0, min(value / goal, 1.0))
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def agent_choices() -> list[app_commands.Choice[str]]:
    db = SessionLocal()
    try:
        agents = db.scalars(select(Agent).order_by(Agent.name)).all()
        return [app_commands.Choice(name=a.name, value=a.name) for a in agents[:25]]
    finally:
        db.close()


async def agent_autocomplete(interaction: discord.Interaction, current: str):
    db = SessionLocal()
    try:
        agents = db.scalars(
            select(Agent)
            .where(Agent.name.ilike(f"%{current}%"))
            .order_by(Agent.name)
            .limit(25)
        ).all()
        return [app_commands.Choice(name=a.name, value=a.name) for a in agents]
    finally:
        db.close()


def get_agent(db, name: str) -> Agent | None:
    return db.scalar(select(Agent).where(Agent.name == name))


def month_bounds(year: int, month: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def approved_deal_filter():
    # Normalize the status so values like "Approved", "approved", etc.
    # are all treated as approved sales.
    return func.lower(func.trim(Deal.status)) == "approved"


def stats_for_agent(db, agent_id: int, year: int, month: int):
    # Deal.date is stored as a timestamp. Using the timestamp range here keeps
    # monthly statistics independent from the exact time of day.
    start, end = month_bounds(year, month)
    filters = (
        Deal.agent_id == agent_id,
        Deal.date >= start,
        Deal.date < end,
        approved_deal_filter(),
    )

    total = db.scalar(
        select(func.coalesce(func.sum(Deal.annual_premium), 0)).where(*filters)
    ) or 0
    count = db.scalar(
        select(func.count(Deal.id)).where(*filters)
    ) or 0
    return float(total), int(count)


def today_stats(db, agent_id: int, reference_date=None):
    # Compare the calendar date rather than relying on the machine timezone.
    # This is important when Discord/Postgres and the bot run in different
    # timezones. PostgreSQL's date() returns the calendar date represented by
    # the stored timestamp.
    target_date = reference_date or local_today()
    date_expr = func.date(Deal.date)
    filters = (
        Deal.agent_id == agent_id,
        date_expr == target_date,
        approved_deal_filter(),
    )

    total = db.scalar(
        select(func.coalesce(func.sum(Deal.annual_premium), 0)).where(*filters)
    ) or 0
    count = db.scalar(
        select(func.count(Deal.id)).where(*filters)
    ) or 0
    return float(total), int(count)


def get_goal(db, agent_id: int, year: int, month: int) -> float:
    goal = db.scalar(select(AgentGoal).where(
        AgentGoal.agent_id == agent_id,
        AgentGoal.year == year,
        AgentGoal.month == month,
    ))
    return float(goal.amount) if goal else 0.0


def sale_embed(db, deal: Deal) -> discord.Embed:
    agent = db.get(Agent, deal.agent_id)

    status = (deal.status or "").strip().lower()
    status_icon = (
        "✅" if status == "approved"
        else "🕐" if status == "pending"
        else "❌" if status in {"cancelled", "canceled", "rejected"}
        else "•"
    )

    embed = discord.Embed(
        title="💰 New Sale",
        description=f"**{agent.name if agent else 'Unknown agent'}**",
    )
    # Keep short metadata together; long descriptive values get their own rows.
    embed.add_field(name="AP", value=money(deal.annual_premium), inline=True)
    embed.add_field(
        name="Date",
        value=(
            deal.date.strftime("%b %-d, %Y")
            if os.name != "nt"
            else deal.date.strftime("%b %#d, %Y")
        ),
        inline=True,
    )
    embed.add_field(name="Status", value=f"{status_icon} {deal.status}", inline=True)
    embed.add_field(name="Carrier", value=deal.carrier or "—", inline=False)
    embed.add_field(name="Product", value=deal.product or "—", inline=False)
    embed.set_footer(text=f"GuildPilot • Deal #{deal.id}")
    return embed


def sale_view(deal_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Open the live board ↗", style=discord.ButtonStyle.link, url=settings.LIVE_BOARD_URL))
    return view


class SaleModal(discord.ui.Modal, title="New Sale"):
    def __init__(self, agent_name: str, deal: Deal | None = None):
        super().__init__()
        self.agent_name = agent_name
        self.deal = deal
        self.client_name = discord.ui.TextInput(label="Client", required=True, max_length=100, default=(deal.client if deal else ""))
        self.carrier = discord.ui.TextInput(label="Carrier", required=True, max_length=100, default=(deal.carrier if deal else ""))
        self.product = discord.ui.TextInput(label="Product", required=True, max_length=20, default=(deal.product if deal else ""))
        self.ap = discord.ui.TextInput(label="Annual Premium", required=True, max_length=20, default=(str(deal.annual_premium) if deal else ""), placeholder="1200")
        existing_note = ""
        if deal is not None:
            note_db = SessionLocal()
            try:
                note_row = note_db.scalar(select(DealNote).where(DealNote.deal_id == deal.id))
                existing_note = note_row.text if note_row else ""
            finally:
                note_db.close()
        self.notes = discord.ui.TextInput(label="Notes", required=False, style=discord.TextStyle.paragraph, max_length=1000, default=existing_note)
        for item in (self.client_name, self.carrier, self.product, self.ap, self.notes):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            premium = float(self.ap.value.replace(",", "").replace("$", "").strip())
            if premium <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Annual Premium must be a positive number.", ephemeral=True)
            return

        db = SessionLocal()
        try:
            agent = get_agent(db, self.agent_name)
            if agent is None:
                await interaction.response.send_message(f"Agent `{self.agent_name}` not found.", ephemeral=True)
                return

            now = local_now().replace(tzinfo=None)
            if self.deal is None:
                deal = Deal(
                    date=now,
                    agent_id=agent.id,
                    client=self.client_name.value.strip(),
                    carrier=self.carrier.value.strip(),
                    product=self.product.value.strip(),
                    annual_premium=premium,
                    term_months=12,
                    status="Pending",
                    policy_number=f"MANUAL-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
                    data_type=MANUAL_SOURCE,
                )
                db.add(deal)
                db.flush()
            else:
                deal = db.get(Deal, self.deal.id)
                if deal is None:
                    await interaction.response.send_message("Deal no longer exists.", ephemeral=True)
                    return
                deal.client = self.client_name.value.strip()
                deal.carrier = self.carrier.value.strip()
                deal.product = self.product.value.strip()
                deal.annual_premium = premium
                deal.data_type = MANUAL_SOURCE

            note = db.scalar(select(DealNote).where(DealNote.deal_id == deal.id))
            if self.notes.value.strip():
                if note is None:
                    note = DealNote(deal_id=deal.id, text=self.notes.value.strip())
                    db.add(note)
                else:
                    note.text = self.notes.value.strip()
            elif note is not None:
                db.delete(note)

            db.flush()
            await publish_or_update_card(db, interaction.client, deal)
            db.commit()

            await interaction.response.send_message(
                f"Sale #{deal.id} {'updated' if self.deal else 'created'}.",
                ephemeral=True,
            )
        except Exception:
            db.rollback()
            logger.exception("Could not save or publish manual sale")
            await interaction.response.send_message(
                "Could not save the sale. Check the application logs for details.",
                ephemeral=True,
            )
        finally:
            db.close()


async def publish_or_update_card(db, client: discord.Client, deal: Deal):
    # SessionLocal uses autoflush=False. Flush pending status/field changes
    # before calculating statistics for the card, otherwise /approve can
    # render the old Pending state in the totals query.
    db.flush()

    post = db.scalar(select(DealPost).where(DealPost.deal_id == deal.id))
    embed = sale_embed(db, deal)
    view = sale_view(deal.id)

    if post and post.discord_message_id:
        channel = client.get_channel(int(post.channel_id)) or await client.fetch_channel(int(post.channel_id))
        try:
            message = await channel.fetch_message(int(post.discord_message_id))
            await message.edit(embed=embed, view=view)
            return
        except discord.NotFound:
            pass

    # The configured target channel is only required when creating a new
    # Discord card (or replacing a missing one). Updating an existing card
    # uses the channel ID stored with its DealPost record.
    channel_id = settings.ROSA_DISCORD_CHANNEL_ID
    if not channel_id:
        raise RuntimeError("ROSA_DISCORD_CHANNEL_ID is not set")

    channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
    message = await channel.send(embed=embed, view=view)

    if post is None:
        post = DealPost(
            deal_id=deal.id,
            agent_id=deal.agent_id,
            channel_id=str(channel.id),
            discord_message_id=str(message.id),
        )
        db.add(post)
    else:
        post.channel_id = str(channel.id)
        post.discord_message_id = str(message.id)
        post.posted_at = utc_now()


async def delete_sale_card(client: discord.Client, post: DealPost | None) -> None:
    """Delete the Discord card if it still exists. Missing cards are harmless."""
    if not post or not post.discord_message_id:
        return

    channel = client.get_channel(int(post.channel_id)) or await client.fetch_channel(int(post.channel_id))
    try:
        message = await channel.fetch_message(int(post.discord_message_id))
        await message.delete()
    except discord.NotFound:
        pass


class SalesCommands:
    def __init__(self, client: discord.Client):
        self.client = client
        self.tree = getattr(client, "tree", None)

    def register(self, tree: app_commands.CommandTree):
        @tree.command(name="sale", description="Create a new sale card for your Discord account")
        async def sale(interaction: discord.Interaction):
            db = SessionLocal()
            try:
                member_name = getattr(interaction.user, "global_name", None) or interaction.user.display_name
                agent = get_or_create_discord_agent(db, interaction.user.id, member_name)
                db.commit()
                await interaction.response.send_modal(SaleModal(agent.name))
            except Exception:
                db.rollback()
                logger.exception("Could not resolve Discord member to sales agent")
                await interaction.response.send_message(
                    "Could not prepare your sales profile. Check the application logs.",
                    ephemeral=True,
                )
            finally:
                db.close()

        @tree.command(name="edit", description="Edit a sale")
        @app_commands.checks.has_permissions(manage_messages=True)
        @app_commands.describe(deal_id="Sale ID")
        async def edit(interaction: discord.Interaction, deal_id: int):
            db = SessionLocal()
            try:
                deal = db.get(Deal, deal_id)
                if deal is None:
                    await interaction.response.send_message(f"Sale #{deal_id} not found.", ephemeral=True)
                    return
                if deal.data_type != MANUAL_SOURCE:
                    await interaction.response.send_message("Imported sales are read-only. Only manual Discord sales can be edited.", ephemeral=True)
                    return
                # The modal reuses the existing DealPost, so submitting it edits the
                # original Discord card instead of creating a second card.
                await interaction.response.send_modal(SaleModal(deal.agent.name, deal))
            finally:
                db.close()

        @tree.command(name="approve", description="Approve a pending sale")
        @app_commands.checks.has_permissions(manage_messages=True)
        @app_commands.describe(deal_id="Sale ID")
        async def approve(interaction: discord.Interaction, deal_id: int):
            db = SessionLocal()
            try:
                deal = db.get(Deal, deal_id)
                if deal is None:
                    await interaction.response.send_message(f"Sale #{deal_id} not found.", ephemeral=True)
                    return
                
                status = (deal.status or "").strip().lower()

                if status != "pending":
                    await interaction.response.send_message(
                        f"Sale #{deal.id} cannot be approved. "
                        f"Current status: {deal.status}. "
                        "Only pending sales can be approved.",
                        ephemeral=True,
                    )
                    return
                
                deal.status = "Approved"
                await publish_or_update_card(db, interaction.client, deal)
                db.commit()
                await interaction.response.send_message(f"Sale #{deal.id} approved.", ephemeral=True)
            except Exception:
                db.rollback()
                logger.exception("Sale approval failed (deal_id=%s)", deal_id)
                await interaction.response.send_message(
                    "Approval failed. Check the application logs for details.",
                    ephemeral=True,
                )
            finally:
                db.close()

        @tree.command(name="undo", description="Cancel a manually created sale")
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.describe(deal_id="Sale ID")
        async def undo(interaction: discord.Interaction, deal_id: int):
            db = SessionLocal()
            try:
                # The service locks the deal row, validates its source/status,
                # and cancels all active schedules in the same transaction.
                try:
                    deal, post = cancel_manual_deal(db, deal_id)
                except LookupError as exc:
                    await interaction.response.send_message(str(exc), ephemeral=True)
                    return
                except ValueError as exc:
                    await interaction.response.send_message(str(exc), ephemeral=True)
                    return

                # Preserve the deal and its related records for audit/history.
                db.commit()

                # Update the existing Discord card after the DB cancellation
                # is durable. A card-update failure must not undo cancellation.
                card_warning = None
                if post is not None:
                    try:
                        await publish_or_update_card(db, interaction.client, deal)
                        db.commit()
                    except Exception:
                        db.rollback()
                        logger.exception(
                            "Cancelled sale card refresh failed (deal_id=%s)",
                            deal_id,
                        )
                        card_warning = (
                            "The database was updated, but the Discord card "
                            "could not be refreshed. Check application logs."
                        )

                response = f"Sale #{deal_id} cancelled. History has been preserved."
                if card_warning:
                    response += f" {card_warning}"
                await interaction.response.send_message(response, ephemeral=True)
            except Exception:
                db.rollback()
                logger.exception("Sale cancellation failed (deal_id=%s)", deal_id)
                await interaction.response.send_message(
                    "Cancellation failed. Check the application logs for details.",
                    ephemeral=True,
                )
            finally:
                db.close()

        @tree.command(name="board", description="Show the live sales board")
        async def board(interaction: discord.Interaction):
            db = SessionLocal()
            try:
                now = local_now().replace(tzinfo=None)
                start, end = month_bounds(now.year, now.month)
                rows = db.execute(
                    select(
                        Agent,
                        func.coalesce(func.sum(Deal.annual_premium), 0).label("total"),
                        func.count(Deal.id).label("count"),
                    )
                    .outerjoin(
                        Deal,
                        (Deal.agent_id == Agent.id)
                        & (Deal.date >= start)
                        & (Deal.date < end)
                        & approved_deal_filter(),
                    )
                    .group_by(Agent.id)
                    .order_by(func.coalesce(func.sum(Deal.annual_premium), 0).desc(), Agent.name)
                ).all()

                embed = discord.Embed(
                    title="🏆 Live Sales Board",
                    description=f"**{now.strftime('%B %Y')}** · approved sales",
                )
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for i, (agent, total, count) in enumerate(rows[:10], 1):
                    total = float(total or 0)
                    count = int(count or 0)
                    goal_amount = get_goal(db, agent.id, now.year, now.month)
                    prefix = medals.get(i, f"**{i}.**")
                    sales_word = "sale" if count == 1 else "sales"
                    if goal_amount:
                        pct = total / goal_amount * 100
                        value = (
                            f"{money(total)} · {count} {sales_word}\n"
                            f"`{progress_bar(total, goal_amount)}` {pct:.0f}% of {money(goal_amount)}"
                        )
                    else:
                        value = f"{money(total)} · {count} {sales_word} · no goal set"
                    embed.add_field(name=f"{prefix} {agent.name}", value=value, inline=False)

                if not rows:
                    embed.description += "\n\nNo agents found."
                await interaction.response.send_message(embed=embed)
            finally:
                db.close()

        @tree.command(name="goal", description="Set a monthly sales goal")
        @app_commands.checks.has_permissions(manage_messages=True)
        @app_commands.describe(agent="Agent", amount="Monthly goal in dollars")
        @app_commands.autocomplete(agent=agent_autocomplete)
        async def goal(interaction: discord.Interaction, agent: str, amount: float):
            if amount < 0:
                await interaction.response.send_message("Goal cannot be negative.", ephemeral=True)
                return
            db = SessionLocal()
            try:
                obj = get_agent(db, agent)
                if obj is None:
                    await interaction.response.send_message(f"Agent `{agent}` not found.", ephemeral=True)
                    return
                now = local_now().replace(tzinfo=None)
                row = db.scalar(select(AgentGoal).where(AgentGoal.agent_id == obj.id, AgentGoal.year == now.year, AgentGoal.month == now.month))
                if row is None:
                    row = AgentGoal(agent_id=obj.id, year=now.year, month=now.month, amount=amount)
                    db.add(row)
                else:
                    row.amount = amount
                db.commit()
                await interaction.response.send_message(f"{agent}'s monthly goal is now {money(amount)}.", ephemeral=True)
            finally:
                db.close()

        @tree.command(name="mystats", description="Show an agent's sales statistics")
        @app_commands.describe(agent="Agent")
        @app_commands.autocomplete(agent=agent_autocomplete)
        async def mystats(interaction: discord.Interaction, agent: str):
            db = SessionLocal()
            try:
                obj = get_agent(db, agent)
                if obj is None:
                    await interaction.response.send_message(f"Agent `{agent}` not found.", ephemeral=True)
                    return
                now = local_now().replace(tzinfo=None)
                monthly_total, monthly_count = stats_for_agent(db, obj.id, now.year, now.month)
                today_total, today_count = today_stats(db, obj.id)
                target = get_goal(db, obj.id, now.year, now.month)
                today_word = "sale" if today_count == 1 else "sales"
                month_word = "sale" if monthly_count == 1 else "sales"
                desc = (
                    f"**Today**\n{money(today_total)} · {today_count} {today_word}\n\n"
                    f"**{now.strftime('%B')}**\n{money(monthly_total)} · {monthly_count} {month_word}"
                )
                if target:
                    pct = monthly_total / target * 100
                    desc += (
                        f"\n\n**Monthly goal**\n"
                        f"{money(monthly_total)} / {money(target)} · **{pct:.0f}%**\n"
                        f"`{progress_bar(monthly_total, target)}`"
                    )
                else:
                    desc += "\n\n**Monthly goal**\nNot set"
                embed = discord.Embed(title=f"📊 {agent}", description=desc)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            finally:
                db.close()

        @tree.command(name="profile", description="Show your Discord-linked agent profile")
        async def profile(interaction: discord.Interaction):
            db = SessionLocal()
            try:
                member_name = (
                    getattr(interaction.user, "global_name", None)
                    or interaction.user.display_name
                )
                obj = get_or_create_discord_agent(
                    db,
                    interaction.user.id,
                    member_name,
                )
                db.commit()

                profile_obj = obj.profile
                description = f"**Agent:** {obj.name}\\n"
                description += f"**Discord:** {interaction.user.mention}\\n"
                if profile_obj:
                    description += (
                        f"**Language:** {profile_obj.language}\\n"
                        f"**Daily limit:** {profile_obj.daily_limit}\\n"
                        f"**Enabled:** {'Yes' if profile_obj.enabled else 'No'}"
                    )
                embed = discord.Embed(
                    title="👤 Your Agent Profile",
                    description=description,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception:
                db.rollback()
                logger.exception("Could not resolve Discord member profile")
                await interaction.response.send_message(
                    "Could not load your profile. Check the application logs.",
                    ephemeral=True,
                )
            finally:
                db.close()

async def handle_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use this command."

    elif isinstance(error, app_commands.CheckFailure):
        message = "You are not allowed to use this command."

    else:
        raise error

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )