"""Seed default data

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:01:00.000000

This migration seeds:
- Admin user (for bootstrap)
- Default work codes
- Default business rules
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get schema from config
settings = get_settings()
SCHEMA = settings.db_schema


# Define tables for data operations
employees = table(
    'employees',
    column('employee_id', sa.Integer),
    column('username', sa.String),
    column('display_name', sa.String),
    column('email', sa.String),
    column('role', sa.String),
    column('is_active', sa.Boolean),
    column('created_at', sa.DateTime),
    schema=SCHEMA,
)

work_codes = table(
    'work_codes',
    column('work_code_id', sa.Integer),
    column('code', sa.String),
    column('description', sa.String),
    column('code_type', sa.String),
    column('sort_order', sa.Integer),
    column('is_active', sa.Boolean),
    column('created_at', sa.DateTime),
    column('created_by', sa.Integer),
    schema=SCHEMA,
)

business_rules = table(
    'business_rules',
    column('rule_id', sa.Integer),
    column('rule_key', sa.String),
    column('rule_value', sa.String),
    column('description', sa.String),
    column('value_type', sa.String),
    column('valid_options', sa.String),
    column('modified_at', sa.DateTime),
    column('modified_by', sa.Integer),
    schema=SCHEMA,
)


def upgrade() -> None:
    # Insert admin user first (ID will be 1)
    op.bulk_insert(
        employees,
        [
            {
                'username': 'admin',
                'display_name': 'System Administrator',
                'email': 'dhaueter@cityofmadison.com',
                'role': 'admin',
                'is_active': True,
                'created_at': datetime.now(),
            }
        ]
    )
    
    # Insert default work codes (created_by = 1, the admin)
    op.bulk_insert(
        work_codes,
        [
            {'code': 'REG', 'description': 'Regular Hours', 'code_type': 'work', 'sort_order': 1, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'OT', 'description': 'Overtime', 'code_type': 'work', 'sort_order': 2, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'TRAINING', 'description': 'Training', 'code_type': 'work', 'sort_order': 3, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'VAC', 'description': 'Vacation', 'code_type': 'leave_paid', 'sort_order': 10, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'SICK', 'description': 'Sick Leave', 'code_type': 'leave_paid', 'sort_order': 11, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'PERSONAL', 'description': 'Personal Day', 'code_type': 'leave_paid', 'sort_order': 12, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'HOLIDAY', 'description': 'Holiday', 'code_type': 'leave_paid', 'sort_order': 13, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'JURY', 'description': 'Jury Duty', 'code_type': 'leave_paid', 'sort_order': 14, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'BEREAVEMENT', 'description': 'Bereavement', 'code_type': 'leave_paid', 'sort_order': 15, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
            {'code': 'LWOP', 'description': 'Leave Without Pay', 'code_type': 'leave_unpaid', 'sort_order': 20, 'is_active': True, 'created_at': datetime.now(), 'created_by': 1},
        ]
    )
    
    # Insert default business rules
    op.bulk_insert(
        business_rules,
        [
            {'rule_key': 'standard_work_week_hours', 'rule_value': '40', 'description': 'Standard number of hours in a work week', 'value_type': 'integer', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'overtime_daily_threshold', 'rule_value': '8', 'description': 'Hours per day before overtime kicks in (0 to disable daily OT)', 'value_type': 'integer', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'overtime_weekly_threshold', 'rule_value': '40', 'description': 'Hours per week before overtime kicks in', 'value_type': 'integer', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'pay_period_type', 'rule_value': 'biweekly', 'description': 'Pay period frequency', 'value_type': 'choice', 'valid_options': 'weekly,biweekly,semimonthly,monthly', 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'week_start_day', 'rule_value': 'sunday', 'description': 'First day of the work week (for overtime calculations)', 'value_type': 'choice', 'valid_options': 'sunday,monday,saturday', 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'max_hours_per_day', 'rule_value': '24', 'description': 'Maximum hours that can be entered for a single day', 'value_type': 'integer', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'allow_future_entries', 'rule_value': 'false', 'description': 'Whether employees can enter time for future dates', 'value_type': 'boolean', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
            {'rule_key': 'entry_lookback_days', 'rule_value': '14', 'description': 'How many days back employees can create/edit entries (0 for unlimited)', 'value_type': 'integer', 'valid_options': None, 'modified_at': datetime.now(), 'modified_by': 1},
        ]
    )


def downgrade() -> None:
    # Delete in reverse order of foreign key dependencies
    table_prefix = f"{SCHEMA}." if SCHEMA else ""
    op.execute(f"DELETE FROM {table_prefix}business_rules")
    op.execute(f"DELETE FROM {table_prefix}work_codes")
    op.execute(f"DELETE FROM {table_prefix}employees WHERE username = 'admin'")