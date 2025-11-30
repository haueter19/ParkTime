"""Add start_time and end_time to time_entries

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 00:03:00.000000

This migration:
1. Adds start_time and end_time columns (nullable initially)
2. Makes hours column nullable (will be computed from times)
3. For existing data, estimates times based on hours (8am start)
4. Makes start_time and end_time required after data migration
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE: Do not import app.config at module import time; resolve schema at runtime


def upgrade() -> None:
    # Resolve schema at runtime
    try:
        from app.config import get_settings
        settings = get_settings()
        SCHEMA = settings.db_schema
    except Exception:
        SCHEMA = None

    # Add new time columns as nullable first
    op.add_column('time_entries', 
                  sa.Column('start_time', sa.DateTime(), nullable=True), 
                  schema=SCHEMA)
    op.add_column('time_entries', 
                  sa.Column('end_time', sa.DateTime(), nullable=True), 
                  schema=SCHEMA)
    
    # Make hours nullable (will be computed from times going forward)
    op.alter_column('time_entries', 'hours',
                    existing_type=sa.Numeric(precision=4, scale=2),
                    nullable=True,
                    schema=SCHEMA)
    
    # Migrate existing data - estimate times based on hours
    # Assume 8:00 AM start time for all existing entries
    # SCHEMA is already resolved above

    connection = op.get_bind()
    
    if SCHEMA:
        time_entries_table = f"{SCHEMA}.time_entries"
    else:
        time_entries_table = "time_entries"
    
    # SQL Server: Create start_time and end_time based on entry_date + hours
    # Start at 8:00 AM, end at start + hours
    connection.execute(sa.text(f"""
        UPDATE {time_entries_table}
        SET 
            start_time = DATEADD(HOUR, 8, CAST(entry_date AS DATETIME)),
            end_time = DATEADD(MINUTE, CAST(hours * 60 AS INT), 
                              DATEADD(HOUR, 8, CAST(entry_date AS DATETIME)))
        WHERE start_time IS NULL
    """))
    
    # Now make the time columns non-nullable
    op.alter_column('time_entries', 'start_time',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    schema=SCHEMA)
    op.alter_column('time_entries', 'end_time',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    schema=SCHEMA)
    
    # Add indexes for querying by time
    op.create_index('ix_time_entries_start_time', 'time_entries', 
                    ['start_time'], schema=SCHEMA)


def downgrade() -> None:
    # Resolve schema at runtime
    try:
        from app.config import get_settings
        settings = get_settings()
        SCHEMA = settings.db_schema
    except Exception:
        SCHEMA = None

    # Remove indexes
    op.drop_index('ix_time_entries_start_time', 'time_entries', schema=SCHEMA)
    
    # Recalculate hours from times for any entries that have NULL hours
    try:
        from app.config import get_settings
        settings = get_settings()
        SCHEMA = settings.db_schema
    except Exception:
        SCHEMA = None

    connection = op.get_bind()
    
    if SCHEMA:
        time_entries_table = f"{SCHEMA}.time_entries"
    else:
        time_entries_table = "time_entries"
    
    connection.execute(sa.text(f"""
        UPDATE {time_entries_table}
        SET hours = CAST(DATEDIFF(MINUTE, start_time, end_time) AS DECIMAL(4,2)) / 60.0
        WHERE hours IS NULL
    """))
    
    # Make hours non-nullable again
    op.alter_column('time_entries', 'hours',
                    existing_type=sa.Numeric(precision=4, scale=2),
                    nullable=False,
                    schema=SCHEMA)
    
    # Drop new columns
    op.drop_column('time_entries', 'end_time', schema=SCHEMA)
    op.drop_column('time_entries', 'start_time', schema=SCHEMA)