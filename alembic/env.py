"""
ParkTime - Alembic Environment Configuration

This module configures Alembic to:
1. Use the database connection from app config
2. Import all models for autogenerate support
3. Handle SQL Server specific migrations
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import app config and models
from app.config import get_settings
from app.models.base import Base
from app.models.employee import Employee
from app.models.work_code import WorkCode
from app.models.time_entry import TimeEntry
from app.models.business_rule import BusinessRule
from app.models.audit_log import AuditLog
from app.models.user_session import UserSession

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from app config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQL Server specific
        compare_type=True,
        compare_server_default=True,
        # Include schema from metadata
        include_schemas=True,
        version_table_schema=settings.db_schema,        
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQL Server specific options
            compare_type=True,
            compare_server_default=True,
            # Include schema from metadata
            include_schemas=False,
            version_table_schema=settings.db_schema,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
