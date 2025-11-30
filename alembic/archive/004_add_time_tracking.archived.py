"""ARCHIVED: 004_add_time_tracking.py

This file was removed from alembic/versions and archived after merging
its contents into 20250101_0002_004_add_time_columns.py to resolve
duplicate revision id '004' (two separate files used the same revision id).

Original contents retained here for history.
"""

"""
Add start_time and end_time to time_entries

Revision ID: 004
Revises: 003
Create Date: 2025-01-02 00:00:00.000000

This migration:
1. Adds start_time and end_time columns (datetime)
2. Makes hours column nullable (will be calculated from times)
3. Adds computed column for calculated_hours (optional)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get schema from config
settings = get_settings()
SCHEMA = settings.db_schema


def upgrade() -> None:
    # Add start_time and end_time columns
    op.add_column('time_entries', 
                  sa.Column('start_time', sa.DateTime(), nullable=True), 
                  schema=SCHEMA)
    op.add_column('time_entries', 
                  sa.Column('end_time', sa.DateTime(), nullable=True), 
                  schema=SCHEMA)
    
    # Make hours nullable (it can be calculated from times or entered directly)
    op.alter_column('time_entries', 'hours',
                    existing_type=sa.Numeric(precision=4, scale=2),
                    nullable=True,
                    schema=SCHEMA)


def downgrade() -> None:
    # Make hours required again
    op.alter_column('time_entries', 'hours',
                    existing_type=sa.Numeric(precision=4, scale=2),
                    nullable=False,
                    schema=SCHEMA)
    
    # Drop the time columns
    op.drop_column('time_entries', 'end_time', schema=SCHEMA)
    op.drop_column('time_entries', 'start_time', schema=SCHEMA)
