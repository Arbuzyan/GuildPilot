import asyncio

import discord
from discord import app_commands
from app.config import settings
from sqlalchemy import select

from app.discord.sales_commands import (
    SalesCommands,
    handle_app_command_error,
)
from app.db.database import SessionLocal
from app.db.models import Agent, AgentProfile
from app.bootstrap import bootstrap_application_data
from app.deals.scheduler import scheduler_loop
from app.deals.service import (
    format_deal_for_ai,
    get_latest_deal,
)

from app.discord.sales_publisher import publish_next_deal
from app.discord.history import (
    get_conversation_history,
    save_message,
)
from app.ai.client import generate_response




intents = discord.Intents.default()
intents.message_content = True


client = discord.Client(
    intents=intents
)
tree = app_commands.CommandTree(client)
SalesCommands(client).register(tree)
tree.on_error = handle_app_command_error

def get_rosa_profile() -> AgentProfile:
    db = SessionLocal()

    try:
        profile = db.scalar(
            select(AgentProfile)
            .join(Agent)
            .where(
                Agent.name == "Rosa Delgado"
            )
        )

        if profile is None:
            raise RuntimeError(
                "Rosa Delgado profile not found"
            )

        return profile

    finally:
        db.close()


def get_latest_deal_context(
    agent_name: str,
) -> str:

    db = SessionLocal()

    try:
        deal = get_latest_deal(
            db,
            agent_name,
        )

        if deal is None:
            return "No verified deal data was found."

        return format_deal_for_ai(deal)

    finally:
        db.close()


@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.online)
    print(f"Logged in as {client.user} (ID: {client.user.id})")

    guild_id = settings.DISCORD_GUILD_ID
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print(f"[COMMANDS] Synced to guild {guild_id}")
    else:
        await tree.sync()
        print("[COMMANDS] Synced globally")

    if not hasattr(client, "scheduler_task"):
        client.scheduler_task = asyncio.create_task(
            scheduler_loop(
                client=client,
                check_interval_seconds=30,
            )
        )

        print("[SCHEDULER] Started")


@client.event
async def on_message(message: discord.Message):
    
    # Не отвечаем сами себе
    if message.author == client.user or message.author.bot:
        return

    print(
        f"[MESSAGE] channel={message.channel.id} "
        f"author={message.author.id}"
    )

    if message.content.lower() == "!postdeal":

        result = await publish_next_deal(
            client,
            "Rosa Delgado",
        )

        await message.channel.send(
            result
        )

        return

    # Пока используем команду !rosa
    if not message.content.lower().startswith("!rosa"):
        return

    profile = get_rosa_profile()

    # Убираем !rosa
    user_message = message.content[5:].strip()

    if not user_message:
        user_message = (
            "Hello! Start a natural conversation."
        )

    # Получаем ID канала и пользователя Discord
    channel_id = str(message.channel.id)
    user_id = str(message.author.id)

    # Сохраняем оригинальное сообщение пользователя
    db = SessionLocal()

    try:
        save_message(
            db=db,
            agent_id=profile.agent_id,
            channel_id=channel_id,
            user_id=user_id,
            role="user",
            content=user_message,
        )

        # Если пользователь спрашивает о последней сделке
        if "latest deal" in user_message.lower():

            deal_context = get_latest_deal_context(
                "Rosa Delgado"
            )

            ai_user_message = (
                f"{user_message}\n\n"
                "Use the following verified database "
                "information when answering:\n\n"
                f"{deal_context}\n\n"
                "Do not invent or alter any deal facts."
            )

        else:
            ai_user_message = user_message

        # Получаем историю после сохранения сообщения
        history = get_conversation_history(
            db=db,
            agent_id=profile.agent_id,
            channel_id=channel_id,
            limit=10,
        )

        # Для текущего сообщения заменяем его обычный текст
        # на AI-контекст, если это запрос о сделке.
        if "latest deal" in user_message.lower():
            history[-1]["content"] = ai_user_message

        try:
            # Anthropic's synchronous SDK must not block Discord's event loop.
            response = await asyncio.to_thread(
                generate_response,
                system_prompt=profile.system_prompt,
                messages=history,
            )
        except Exception as error:
            print(
                f"[AI] Response generation failed: "
                f"{type(error).__name__}: {error}"
            )
            await message.channel.send(
                "I'm having trouble generating a response right now. "
                "Please try again in a moment."
            )
            return

        # Сохраняем ответ Rosa
        save_message(
            db=db,
            agent_id=profile.agent_id,
            channel_id=channel_id,
            user_id=str(client.user.id),
            role="assistant",
            content=response,
        )

    finally:
        db.close()

    await message.channel.send(response)


def main() -> None:
    token = settings.ROSA_DISCORD_TOKEN

    if not token:
        raise RuntimeError(
            "ROSA_DISCORD_TOKEN is not set. "
            "Check your .env file."
        )

    # Ensure the configured pilot agents exist on a fresh installation.
    # The operation is idempotent and does not overwrite existing profiles.
    created = bootstrap_application_data()
    print(f"[BOOTSTRAP] Created {created} agent profile(s)")

    client.run(token)


if __name__ == "__main__":
    main()