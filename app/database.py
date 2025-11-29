# ParkTime - Database Setup
# SQLAlchemy engine, session factory, and FastAPI dependencies

from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.config import get_settings
from app.models.base import Base


# Get settings
settings = get_settings()

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug,  # Log SQL in debug mode
)


# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Prevent lazy-load issues after commit
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    Usage in route handlers:
    
        @router.get("/entries")
        def list_entries(db: Session = Depends(get_db)):
            entries = db.query(TimeEntry).all()
            return entries
    
    The session is automatically closed after the request completes,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside of FastAPI requests.
    
    Usage in scripts, CLI commands, or background tasks:
    
        with get_db_context() as db:
            entries = db.query(TimeEntry).all()
            # Session automatically closed when exiting the block
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database schema.
    
    Creates all tables defined in the models.
    
    WARNING: This is for development/testing only.
    In production, use Alembic migrations.
    """
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all tables.
    
    WARNING: Destroys all data. Only for development/testing.
    """
    Base.metadata.drop_all(bind=engine)


def check_connection() -> bool:
    """
    Test the database connection.
    
    Returns True if connection succeeds, raises exception otherwise.
    Useful for health checks and startup verification.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


# Optional: Set SQL Server specific session options
@event.listens_for(engine, "connect")
def set_sql_server_options(dbapi_connection, connection_record):
    """
    Set connection-level options for SQL Server.
    
    This runs once when a new connection is created.
    """
    cursor = dbapi_connection.cursor()
    
    # Use READ COMMITTED SNAPSHOT for better concurrency
    # (Requires database-level setting: ALTER DATABASE parktime SET READ_COMMITTED_SNAPSHOT ON)
    # cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    
    # Set date format for consistency
    cursor.execute("SET DATEFORMAT ymd")
    
    cursor.close()
