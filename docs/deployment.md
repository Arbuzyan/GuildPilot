# GuildPilot Deployment Guide

## Overview

GuildPilot is deployed using Docker Compose.

The deployment consists of two services:

- `postgres` — PostgreSQL 17 database.
- `bot` — Python 3.13 Discord application.

Docker Compose starts PostgreSQL first and waits for its health check before starting the bot.

The PostgreSQL data directory is persisted in the named Docker volume `guildpilot_postgres_data`.

## 1. Requirements

Before deployment, install:

- Docker Desktop or Docker Engine with Docker Compose support.
- Git.
- Access to a Discord server where the bot can be installed.
- A Discord bot application and its token.

Optional:

- An Anthropic API key for AI-powered conversations.

## 2. Get the project

Clone the repository:

```bash
git clone https://github.com/Arbuzyan/GuildPilot.git
cd GuildPilot
```

Alternatively, download a release archive from the project's GitHub Releases page.

## 3. Configure environment variables

Create the environment file from the example:

```bash
copy .env.example .env
```

On Linux or macOS, use:

```bash
cp .env.example .env
```

Edit `.env` and configure the required values.

### 3.1 PostgreSQL settings

| Variable | Description |
|---|---|
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database username |
| `POSTGRES_PASSWORD` | Database password |
| `DATABASE_URL` | SQLAlchemy connection URL |

Use a long, random password. The password in `POSTGRES_PASSWORD` must match the password embedded in `DATABASE_URL`.

For local Python execution, the example connection URL uses `localhost:5434`.

Inside Docker Compose, the bot service receives a database URL that uses the `postgres` service hostname and internal port `5432`.

### 3.2 Discord settings

| Variable | Required | Description |
|---|---|---|
| `ROSA_DISCORD_TOKEN` | Yes | Discord bot token |
| `ROSA_DISCORD_CHANNEL_ID` | For publication | Target channel ID for deal cards |
| `DISCORD_GUILD_ID` | No | Test server ID for guild-specific command synchronization |

The Discord bot must have the permissions and intents required by the enabled features.

The application uses the message content intent. Enable the corresponding privileged intent in the Discord Developer Portal if required by your bot configuration.

### 3.3 AI settings

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Optional | Anthropic API key |
| `ANTHROPIC_MODEL` | No | Model name; defaults to `claude-sonnet-4-6` |

Without an API key, AI-powered responses are unavailable.

### 3.4 Other settings

| Variable | Required | Description |
|---|---|---|
| `LIVE_BOARD_URL` | No | URL displayed by the sale-card button |

The default value is `https://discord.com`.

**Security:** Never commit `.env` or share Discord tokens, database passwords or API keys. Keep `.env.example` limited to placeholder values.

## 4. Start with Docker Compose

Build the bot image and start both services:

```bash
docker compose up -d --build
```

The Compose configuration:

1. Starts PostgreSQL.
2. Waits for the PostgreSQL health check.
3. Builds and starts the bot container.
4. Runs database migrations.
5. Starts the Discord application.

The bot container executes:

```bash
alembic upgrade head && python -m app
```

If the migration command fails, the bot process does not start.

## 5. Verify the deployment

Check service status:

```bash
docker compose ps
```

View PostgreSQL logs:

```bash
docker compose logs postgres
```

View bot logs:

```bash
docker compose logs bot
```

Follow bot logs continuously:

```bash
docker compose logs -f bot
```

A successful deployment should show PostgreSQL as healthy and the bot connecting to Discord.

## 6. Database migrations

Alembic is the only supported schema migration mechanism.

The Docker startup command applies:

```bash
alembic upgrade head
```

To inspect the current migration revision from inside the bot container:

```bash
docker compose exec bot alembic current
```

To inspect available migration history:

```bash
docker compose exec bot alembic history
```

To check whether model metadata differs from the current database schema:

```bash
docker compose exec bot alembic check
```

Do not manually create application tables as a replacement for migrations.

### Existing database warning

Do not point the deployment at an existing populated database without reviewing its schema and Alembic revision first.

If the database has no Alembic version record, do not run `alembic upgrade head` directly against it.

Follow the reviewed adoption procedure in [Database](database.md) and `TIMEZONE_MIGRATION_REQUIRED.md`.

The timezone migration has a specific safety check for historical scheduled publication timestamps. An unexpected populated set of rows causes the migration to abort.

## 7. Run tests

Install dependencies in a local Python environment:

```bash
python -m pip install -r requirements.txt
```

Run the unit test suite:

```bash
python -m unittest discover -s tests -v
```

The GitHub Actions workflow runs this same test command using Python 3.13 on pushes and pull requests targeting `main`.

## 8. Run the Excel importer

Excel import is separate from the Discord bot process.

With the Python environment and database connection configured, run:

```bash
python -m app.main path/to/deals.xlsx
```

Replace the path with the actual workbook path.

The importer opens a database session, imports deals and closes the session.

## 9. Stop and restart services

Stop containers without deleting persistent database data:

```bash
docker compose down
```

Start the existing deployment again:

```bash
docker compose up -d
```

Rebuild the bot image after application changes:

```bash
docker compose up -d --build
```

The named PostgreSQL volume is retained when using `docker compose down`.

**Do not use `docker compose down -v` for routine shutdown.** The `-v` option removes named volumes and can permanently delete the database data stored in them.

## 10. Troubleshooting

### PostgreSQL is not healthy

Inspect its logs:

```bash
docker compose logs postgres
```

Check:

- Whether the database container started.
- Whether the configured password is valid.
- Whether the PostgreSQL health check succeeds.
- Whether another process is already using the published host port `5434`.

### Bot container exits during startup

Inspect the logs:

```bash
docker compose logs bot
```

Check:

- `ROSA_DISCORD_TOKEN` is configured.
- `DATABASE_URL` is valid.
- PostgreSQL is healthy.
- Alembic migrations completed successfully.
- Required environment variables are available inside the container.

### Discord commands do not appear

Check:

- The bot is connected.
- The bot has been invited with the required application command permissions.
- `DISCORD_GUILD_ID` is correct if guild-specific synchronization is used.
- The bot has permission to operate in the target server.

### AI responses are unavailable

Check that `ANTHROPIC_API_KEY` is configured and valid.

Also verify the configured `ANTHROPIC_MODEL` and inspect bot logs for API errors.

### Database migration fails

Do not repeatedly retry a failed migration against a populated database without understanding the error.

Inspect the migration revision and database state. For timezone-related migration failures, review `TIMEZONE_MIGRATION_REQUIRED.md` before taking further action.

## 11. Persistent data and backups

PostgreSQL data is stored in the Docker named volume:

```text
guildpilot_postgres_data
```

The volume survives ordinary container recreation and `docker compose down`.

Back up the database before:

- Applying migrations to an existing database.
- Performing schema adoption.
- Performing a database upgrade or downgrade.
- Making other potentially destructive database changes.

A backup should be validated before it is considered reliable.

Never treat a successful container start as proof that a database backup or migration is safe.

## Related documentation

- [Architecture](architecture.md)
- [Database](database.md)
- [Project README](../README.md)
- [Timezone migration notes](../TIMEZONE_MIGRATION_REQUIRED.md)