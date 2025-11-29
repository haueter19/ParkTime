"""Initial schema - all tables

Revision ID: 001
Revises: 
Create Date: 2025-01-01 00:00:00.000000

This migration creates all initial tables for ParkTime:
- employees: User accounts with roles
- work_codes: Time entry categories
- time_entries: The actual time records
- business_rules: Configuration key-value store
- audit_log: Change tracking
- user_sessions: Authentication sessions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get schema from config
settings = get_settings()
SCHEMA = settings.db_schema  # Will be None for dbo


def upgrade() -> None:
    # Create schema if specified and doesn't exist
    if SCHEMA:
        op.execute(f"IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{SCHEMA}') EXEC('CREATE SCHEMA {SCHEMA}')")
    
    # Employees table
    op.create_table(
        'employees',
        sa.Column('employee_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='employee'),
        sa.Column('manager_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['manager_id'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_employees_manager'),
        sa.ForeignKeyConstraint(['created_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_employees_created_by'),
        sa.PrimaryKeyConstraint('employee_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_employees_username', 'employees', ['username'], unique=True, schema=SCHEMA)
    
    # Work codes table
    op.create_table(
        'work_codes',
        sa.Column('work_code_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('description', sa.String(length=100), nullable=False),
        sa.Column('code_type', sa.String(length=20), nullable=False, server_default='work'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_work_codes_created_by'),
        sa.PrimaryKeyConstraint('work_code_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_work_codes_code', 'work_codes', ['code'], unique=True, schema=SCHEMA)
    
    # Time entries table
    op.create_table(
        'time_entries',
        sa.Column('entry_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('work_code_id', sa.Integer(), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.Column('modified_by', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_time_entries_employee'),
        sa.ForeignKeyConstraint(['work_code_id'], [f'{SCHEMA}.work_codes.work_code_id' if SCHEMA else 'work_codes.work_code_id'], name='fk_time_entries_work_code'),
        sa.ForeignKeyConstraint(['created_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_time_entries_created_by'),
        sa.ForeignKeyConstraint(['modified_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_time_entries_modified_by'),
        sa.ForeignKeyConstraint(['deleted_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_time_entries_deleted_by'),
        sa.PrimaryKeyConstraint('entry_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_time_entries_employee_id', 'time_entries', ['employee_id'], schema=SCHEMA)
    op.create_index('ix_time_entries_work_code_id', 'time_entries', ['work_code_id'], schema=SCHEMA)
    op.create_index('ix_time_entries_employee_date', 'time_entries', ['employee_id', 'entry_date'], schema=SCHEMA)
    op.create_index('ix_time_entries_date', 'time_entries', ['entry_date'], schema=SCHEMA)
    op.create_index('ix_time_entries_is_deleted', 'time_entries', ['is_deleted'], schema=SCHEMA)
    
    # Business rules table
    op.create_table(
        'business_rules',
        sa.Column('rule_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_key', sa.String(length=100), nullable=False),
        sa.Column('rule_value', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False, server_default='string'),
        sa.Column('valid_options', sa.String(length=500), nullable=True),
        sa.Column('modified_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('modified_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['modified_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_business_rules_modified_by'),
        sa.PrimaryKeyConstraint('rule_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_business_rules_rule_key', 'business_rules', ['rule_key'], unique=True, schema=SCHEMA)
    
    # Audit log table
    op.create_table(
        'audit_log',
        sa.Column('audit_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('changed_fields', sa.String(length=500), nullable=True),
        sa.Column('old_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=False),
        sa.Column('performed_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('context', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['performed_by'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_audit_log_performed_by'),
        sa.PrimaryKeyConstraint('audit_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_audit_log_table_name', 'audit_log', ['table_name'], schema=SCHEMA)
    op.create_index('ix_audit_log_record_id', 'audit_log', ['record_id'], schema=SCHEMA)
    op.create_index('ix_audit_log_action', 'audit_log', ['action'], schema=SCHEMA)
    op.create_index('ix_audit_log_performed_by', 'audit_log', ['performed_by'], schema=SCHEMA)
    op.create_index('ix_audit_log_performed_at', 'audit_log', ['performed_at'], schema=SCHEMA)
    
    # User sessions table
    op.create_table(
        'user_sessions',
        sa.Column('session_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('session_token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True),
        sa.Column('logged_out_at', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], [f'{SCHEMA}.employees.employee_id' if SCHEMA else 'employees.employee_id'], name='fk_user_sessions_employee'),
        sa.PrimaryKeyConstraint('session_id'),
        schema=SCHEMA,
    )
    op.create_index('ix_user_sessions_token', 'user_sessions', ['session_token'], unique=True, schema=SCHEMA)
    op.create_index('ix_user_sessions_employee_id', 'user_sessions', ['employee_id'], schema=SCHEMA)
    op.create_index('ix_user_sessions_employee_active', 'user_sessions', ['employee_id', 'is_active'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table('user_sessions', schema=SCHEMA)
    op.drop_table('audit_log', schema=SCHEMA)
    op.drop_table('business_rules', schema=SCHEMA)
    op.drop_table('time_entries', schema=SCHEMA)
    op.drop_table('work_codes', schema=SCHEMA)
    op.drop_table('employees', schema=SCHEMA)