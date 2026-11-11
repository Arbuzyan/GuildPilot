"""Idempotent application data bootstrap for a fresh installation."""
from app.agents.profiles import create_pilot_profiles


def bootstrap_application_data() -> int:
    """Ensure configured pilot agents and profiles exist.

    Returns the number of profiles created. Existing agents and profiles are
    preserved; this function is safe to run on every application start.
    """
    # Import lazily so importing this module in unit tests does not require a
    # configured DATABASE_URL before the bootstrap is actually executed.
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        return create_pilot_profiles(db)
    finally:
        db.close()
