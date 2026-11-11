# GuildPilot

**AI Agents & Discord Automation Platform**

GuildPilot is a Python application for publishing approved sales records to Discord, scheduling transparent posts, and providing an AI-assisted conversational interface grounded in application data.

> **Release status: pre-release candidate.** Do not use this build against a production database until fresh-install and legacy-adoption procedures have been verified.

## What it does

- Runs one explicitly configured Discord bot account.
- Publishes approved deal records to a configured Discord channel.
- Schedules publications using PostgreSQL-backed state.
- Prevents duplicate publication and protects cancelled deals.
- Keeps conversation history and can answer with Anthropic using verified application data.
- Stores absolute timestamps in UTC and interprets scheduling in the host computer's timezone.

The public build excludes the former multi-account reaction/comment automation. It does not simulate team activity or coordinate multiple bot accounts. The `sale_engagements` table remains in the schema for historical compatibility; the public bot does not generate new simulated engagement records.

## Requirements

- Python 3.13
- Docker Desktop with Docker Compose
- PostgreSQL 17 (provided by the included Compose file)
- A Discord application/bot with the Message Content Intent enabled
- An Anthropic API key only if AI responses are enabled

## Setup

1. Clone or download the repository.
2. Copy `.env.example` to `.env`.
3. Set a long PostgreSQL password using letters and digits only, and use the same value in `POSTGRES_PASSWORD` and `DATABASE_URL`. The Docker Compose configuration uses the internal service hostname `postgres`; local Python runs use `localhost`.
4. Add `ROSA_DISCORD_TOKEN`, `ROSA_DISCORD_CHANNEL_ID`, optional `DISCORD_GUILD_ID`, and optionally `ANTHROPIC_API_KEY`. Never commit `.env`.
5. Build and start PostgreSQL plus the bot. The bot waits for the PostgreSQL health check, applies Alembic migrations, and then starts:

   ```bash
   docker compose up --build -d
   docker compose logs -f bot
   ```

The database is published on host port `5434` to avoid colliding with an existing local PostgreSQL container. For local development, start only PostgreSQL with `docker compose up -d postgres`, use `localhost:5434` in `DATABASE_URL`, create and activate a Python 3.13 virtual environment, install dependencies, then migrate and start the bot:

   ```bash
   python -m venv .venv
   # Windows CMD: .venv\Scripts\activate.bat
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   python -m app
   ```

On `/sale` and `/profile`, GuildPilot links the action to the invoking Discord member by their stable Discord user ID. A matching agent/profile is created automatically on first use, and the member's current Discord display name is used as the agent name. Existing seed agents and historical sales remain intact. Enable **Message Content Intent** in the Discord Developer Portal and grant the bot permissions to view channels, send messages, embed links, and use application commands.

## Commands

- `/sale` — create a manual sale card attributed automatically to the invoking Discord member; the resulting card shows the database deal ID in the footer.
- `/edit` — edit a manually created sale (requires Manage Messages).
- `/approve` — approve a pending sale (requires Manage Messages).
- `/undo` — cancel a manually created sale while preserving its history (requires Administrator).
- `/board` — show the live sales board.
- `/goal` — set a monthly sales goal (Manage Messages).
- `/mystats` — show an agent's sales statistics.
- `/profile` — show the profile linked to the invoking Discord user.

The text commands `!rosa` and `!postdeal` are also supported in channels the bot can read.

## Spreadsheet import

Spreadsheet import is optional and explicit. The workbook must contain a `Deals` sheet with the expected columns. Run:

```bash
python -m app.main path/to/deals.xlsx
```

No private workbook is included or imported automatically.

## Database and migration safety

- Alembic is the sole schema-management mechanism; application startup does not call `create_all()`.
- The initial migration creates the full pre-timezone schema. The following migration converts absolute timestamp columns to timezone-aware UTC storage. A later migration adds a unique Discord-user mapping to agent records.
- `deals.date` remains timezone-naive because its historical business meaning has not yet been standardized.
- The legacy `scheduled_at` conversion is intentionally guarded: populated legacy schedules must match the audited historical rows. Unexpected values stop the migration for manual review.
- Schedule planning counts only active schedules, prevents duplicate planning across all active states, and does not consume slots for cancelled or failed schedules.
- Public sale text is derived from stored deal fields; it does not invent approval methods or lead channels.
- Internal exception details are written to application logs rather than sent to Discord users.
- For an existing populated database, do not apply the initial baseline to its tables. Use a reviewed adoption procedure to verify the schema and migration stamp before upgrading. Never stamp an unknown schema automatically.

Always test upgrades on a disposable database and take a verified backup before any production migration.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Check model/migration drift against a configured disposable PostgreSQL database:

```bash
alembic check
```

## Security

- Keep Discord and Anthropic credentials in `.env` only.
- Use a dedicated PostgreSQL role with the minimum required privileges.
- Never commit database dumps, customer data, tokens, or local workbooks.
- Rotate credentials that have appeared in logs, screenshots, or chat.

## License

No license has been selected. Until a license is added, standard copyright applies and reuse/redistribution permissions are not granted by this repository.
