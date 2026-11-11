"""Discord command and card-update integration tests with mocked Discord API.

These tests use an isolated in-memory SQLite database. No live Discord API or
configured PostgreSQL database is contacted.

Run from the project root:
    python -m unittest discover -s tests -p "test_*.py" -v
"""

import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

# sales_commands imports the database module at import time. Supply an isolated
# fallback URL for test environments that do not have a project .env file.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import discord
from discord import app_commands
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Agent, Base, Deal, DealNote, DealPost, ScheduledDealPost
from app.discord import sales_commands


class DiscordIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ.setdefault("ROSA_DISCORD_CHANNEL_ID", "333333333333333333")
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

        with self.Session() as db:
            self.agent = Agent(name="GuildPilot Discord Test Agent")
            db.add(self.agent)
            db.commit()
            self.agent_id = self.agent.id

        self.client = discord.Client(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self.client)
        sales_commands.SalesCommands(self.client).register(self.tree)
        self.undo_command = self.tree.get_command("undo")

    async def asyncTearDown(self) -> None:
        # The client is not logged in, but close it to release resources.
        if not self.client.is_closed():
            await self.client.close()
        self.engine.dispose()

    def make_deal(self, *, source="manual_discord", status="Pending") -> int:
        with self.Session() as db:
            deal = Deal(
                date=datetime.now(),
                agent_id=self.agent_id,
                client="Synthetic Discord Client",
                carrier="TEST",
                product="TEST",
                annual_premium=1.0,
                term_months=12,
                status=status,
                policy_number=f"TEST-DISCORD-{uuid4().hex}",
                data_type=source,
            )
            db.add(deal)
            db.commit()
            return deal.id

    def make_interaction(self):
        response = SimpleNamespace(send_message=AsyncMock(), is_done=lambda: False)
        return SimpleNamespace(response=response, client=SimpleNamespace())

    async def test_undo_command_cancels_and_preserves_related_records(self) -> None:
        deal_id = self.make_deal()
        with self.Session() as db:
            db.add_all([
                DealNote(deal_id=deal_id, text="Synthetic audit note"),
                DealPost(
                    deal_id=deal_id,
                    agent_id=self.agent_id,
                    channel_id="111111111111111111",
                    discord_message_id="222222222222222222",
                ),
                ScheduledDealPost(
                    agent_id=self.agent_id,
                    deal_id=deal_id,
                    scheduled_at=datetime.now() + timedelta(hours=1),
                    status="pending",
                ),
            ])
            db.commit()

        interaction = self.make_interaction()
        with patch.object(sales_commands, "SessionLocal", self.Session), patch.object(
            sales_commands,
            "publish_or_update_card",
            new=AsyncMock(),
        ) as update_card:
            await self.undo_command.callback(interaction, deal_id)

        update_card.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once()
        self.assertIn("cancelled", interaction.response.send_message.await_args.args[0].lower())

        with self.Session() as db:
            deal = db.get(Deal, deal_id)
            self.assertEqual(deal.status, "Cancelled")
            self.assertIsNotNone(db.scalar(select(DealNote).where(DealNote.deal_id == deal_id)))
            self.assertIsNotNone(db.scalar(select(DealPost).where(DealPost.deal_id == deal_id)))
            schedule = db.scalar(
                select(ScheduledDealPost).where(ScheduledDealPost.deal_id == deal_id)
            )
            self.assertEqual(schedule.status, "cancelled")

    async def test_card_refresh_failure_does_not_reverse_database_cancellation(self) -> None:
        deal_id = self.make_deal()
        interaction = self.make_interaction()

        with patch.object(sales_commands, "SessionLocal", self.Session), patch.object(
            sales_commands,
            "publish_or_update_card",
            new=AsyncMock(side_effect=RuntimeError("Discord API unavailable")),
        ):
            # The command only refreshes a card when a DealPost exists.
            with self.Session() as db:
                db.add(DealPost(
                    deal_id=deal_id,
                    agent_id=self.agent_id,
                    channel_id="111111111111111111",
                    discord_message_id="222222222222222222",
                ))
                db.commit()

            await self.undo_command.callback(interaction, deal_id)

        response_text = interaction.response.send_message.await_args.args[0]
        self.assertIn("database was updated", response_text.lower())
        self.assertIn("could not be refreshed", response_text.lower())
        with self.Session() as db:
            self.assertEqual(db.get(Deal, deal_id).status, "Cancelled")

    async def test_undo_command_rejects_imported_deal(self) -> None:
        deal_id = self.make_deal(source="imported", status="Issued")
        interaction = self.make_interaction()

        with patch.object(sales_commands, "SessionLocal", self.Session), patch.object(
            sales_commands,
            "publish_or_update_card",
            new=AsyncMock(),
        ) as update_card:
            await self.undo_command.callback(interaction, deal_id)

        update_card.assert_not_awaited()
        self.assertIn("imported", interaction.response.send_message.await_args.args[0].lower())
        with self.Session() as db:
            self.assertEqual(db.get(Deal, deal_id).status, "Issued")

    async def test_undo_command_permission_check_requires_administrator(self) -> None:
        permission_check = self.undo_command.checks[0]

        regular_user = SimpleNamespace(
            permissions=discord.Permissions(administrator=False)
        )
        administrator = SimpleNamespace(
            permissions=discord.Permissions(administrator=True)
        )

        # discord.py permission checks raise MissingPermissions rather than
        # returning False when the member lacks the required permission.
        with self.assertRaises(discord.app_commands.errors.MissingPermissions):
            permission_check(regular_user)

        self.assertTrue(permission_check(administrator))

    async def test_existing_discord_card_is_edited_not_duplicated(self) -> None:
        deal_id = self.make_deal(status="Cancelled")
        with self.Session() as db:
            post = DealPost(
                deal_id=deal_id,
                agent_id=self.agent_id,
                channel_id="111111111111111111",
                discord_message_id="222222222222222222",
            )
            db.add(post)
            db.commit()

            message = SimpleNamespace(edit=AsyncMock())
            channel = SimpleNamespace(
                fetch_message=AsyncMock(return_value=message),
                send=AsyncMock(),
            )
            client = SimpleNamespace(get_channel=lambda _channel_id: channel)

            with patch.object(sales_commands, "sale_embed", return_value=object()), patch.object(
                sales_commands, "sale_view", return_value=object()
            ):
                await sales_commands.publish_or_update_card(db, client, db.get(Deal, deal_id))

            message.edit.assert_awaited_once()
            channel.send.assert_not_awaited()
            posts = db.scalars(select(DealPost).where(DealPost.deal_id == deal_id)).all()
            self.assertEqual(len(posts), 1)


if __name__ == "__main__":
    unittest.main()
