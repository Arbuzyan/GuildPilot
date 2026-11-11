from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


if not settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured. "
        "Check your .env file."
    )


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()



def dispose_db() -> None:
    """Close all connections in the connection pool."""
    engine.dispose()