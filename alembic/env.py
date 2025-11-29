"""
ParkTime - Alembic Environment Configuration

This module configures Alembic to:
1. Use the database connection from app config
2. Import all models for autogenerate support
3. Handle SQL Server specific migrations
"""

from logging.config import fileConfig

import sqlalchemy as sa
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

# Use set_main_option with raw=True to avoid interpolation issues
if config.config_ini_section:
    # ConfigParser will treat '%' specially (interpolation) so double any
    # percent characters to escape them before writing to the section.
    config.set_section_option(
        config.config_ini_section,
        "sqlalchemy.url",
        settings.database_url.replace('%', '%%'),
    )
else:
    # Fallback: modify the config parser directly with raw interpolation disabled
    config.set_main_option("sqlalchemy.url", settings.database_url.replace('%', '%%'))


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
        # If a schema is configured, try to ensure it exists before Alembic
        # creates the alembic_version table in that schema. If we cannot
        # create/use the schema (lack of permission), fall back to using the
        # default schema for the version table so migrations can proceed.
        version_table_schema = settings.db_schema
        if version_table_schema:
            try:
                connection.execute(
                    sa.text("IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = :s) EXEC('CREATE SCHEMA %s')" % version_table_schema)
                )
            except Exception:
                # Could not create or use the schema (permissions etc.) —
                # log and fallback to default schema for alembic_version
                import logging
                logging.getLogger("alembic.env").warning(
                    "Unable to create/use schema '%s' for alembic_version; falling back to default schema",
                    version_table_schema,
                )
                version_table_schema = None

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQL Server specific options
            compare_type=True,
            compare_server_default=True,
            # Include schema from metadata
            include_schemas=True,
            version_table_schema=version_table_schema,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
