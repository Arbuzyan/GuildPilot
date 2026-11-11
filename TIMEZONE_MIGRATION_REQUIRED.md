# GuildPilot database and timezone migrations

## Revision chain

- `aeb3e4d561c0_initial_database_schema.py` creates the complete initial schema. Its absolute timestamp columns are deliberately naive so the next revision can apply the documented historical interpretation.
- `c41d9e7a2b60_timezone_aware_timestamps.py` converts the six absolute-time columns to PostgreSQL `TIMESTAMP WITH TIME ZONE`; `deals.date` remains unchanged.

## Historical interpretation

- `conversation_messages.created_at`, `deal_notes.updated_at`, `deal_posts.posted_at`, `sale_engagements.engaged_at`, and `scheduled_deal_posts.created_at` are interpreted as UTC.
- `scheduled_deal_posts.scheduled_at` is interpreted as `Europe/Moscow` only when its existing rows exactly match the audited IDs 73, 74, and 75 with their exact original naive timestamps. An empty table is allowed for a fresh installation. Any other populated set aborts the migration before the column conversion; audit those values and define an explicit policy before retrying.
- `deals.date` remains `TIMESTAMP WITHOUT TIME ZONE` because its historical business meaning has not been standardized.

## Fresh installation test

1. Create a new, empty disposable PostgreSQL database.
2. Point `DATABASE_URL` to that database without sharing the URL or password.
3. Run `alembic upgrade head`.
4. Verify the nine application tables, six timezone-aware columns, `deals.date`, and `alembic_version`.
5. Run `alembic check` against the same database.

## Existing database adoption

- If the existing database already has `alembic_version = aeb3e4d561c0`, the baseline is considered applied and Alembic will run only the timezone revision. Verify the full legacy schema before proceeding.
- If the existing database has no Alembic version row, do not run `alembic upgrade head` directly against populated tables. First take and validate a backup, compare every table/column/constraint with the baseline, and only then use a separately reviewed `alembic stamp aeb3e4d561c0` adoption step.
- Never stamp an unknown or partially matching schema.

## Safety

Test upgrade and downgrade on disposable copies only. Never run downgrade or schema migration against the production database without a verified backup, a reviewed rollback plan, and explicit approval. Application startup does not create tables; Alembic is the sole schema manager.
