"""Split employee display_name into first_name and last_name

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:02:00.000000

This migration:
1. Adds first_name and last_name columns
2. Migrates existing display_name data (splits on first space)
3. Drops display_name column
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get schema from config
settings = get_settings()
SCHEMA = settings.db_schema


def upgrade() -> None:
    # Add new columns as nullable first
    op.add_column('employees', sa.Column('first_name', sa.String(length=75), nullable=True), schema=SCHEMA)
    op.add_column('employees', sa.Column('last_name', sa.String(length=75), nullable=True), schema=SCHEMA)
    
    # Migrate data from display_name to first_name/last_name
    # This requires raw SQL since we need to split strings
    connection = op.get_bind()
    
    if SCHEMA:
        employees_table = f"{SCHEMA}.employees"
    else:
        employees_table = "employees"
    
    # SQL Server string splitting logic
    # If display_name has a space, split on first space
    # Otherwise, use entire name as last_name
    connection.execute(sa.text(f"""
        UPDATE {employees_table}
        SET 
            first_name = CASE 
                WHEN CHARINDEX(' ', display_name) > 0 
                THEN LEFT(display_name, CHARINDEX(' ', display_name) - 1)
                ELSE ''
            END,
            last_name = CASE 
                WHEN CHARINDEX(' ', display_name) > 0 
                THEN LTRIM(SUBSTRING(display_name, CHARINDEX(' ', display_name) + 1, LEN(display_name)))
                ELSE display_name
            END
    """))
    
    # Make columns non-nullable (must specify type for SQL Server)
    op.alter_column('employees', 'first_name', 
                    existing_type=sa.String(length=75),
                    nullable=False, 
                    schema=SCHEMA)
    op.alter_column('employees', 'last_name', 
                    existing_type=sa.String(length=75),
                    nullable=False, 
                    schema=SCHEMA)
    
    # Drop old column
    op.drop_column('employees', 'display_name', schema=SCHEMA)


def downgrade() -> None:
    # Add display_name back
    op.add_column('employees', sa.Column('display_name', sa.String(length=150), nullable=True), schema=SCHEMA)
    
    # Migrate data back
    connection = op.get_bind()
    
    if SCHEMA:
        employees_table = f"{SCHEMA}.employees"
    else:
        employees_table = "employees"
    
    connection.execute(sa.text(f"""
        UPDATE {employees_table}
        SET display_name = first_name + ' ' + last_name
    """))
    
    op.alter_column('employees', 'display_name', 
                    existing_type=sa.String(length=150),
                    nullable=False, 
                    schema=SCHEMA)
    
    # Drop new columns
    op.drop_column('employees', 'last_name', schema=SCHEMA)
    op.drop_column('employees', 'first_name', schema=SCHEMA)
