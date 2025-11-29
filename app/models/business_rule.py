# ParkTime - Business Rule Model

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employee import Employee


class BusinessRule(Base):
    """
    Key-value store for configurable business rules.
    
    Examples:
        - standard_work_week_hours: "40"
        - overtime_daily_threshold: "8"
        - overtime_weekly_threshold: "40"
        - pay_period_type: "biweekly"
        - pay_period_start_day: "sunday"
    
    Values are stored as strings and parsed by the application layer.
    This keeps the schema simple while allowing flexible configuration.
    
    For more complex rules (e.g., different thresholds by employee type),
    consider a separate rules engine or extending this model.
    """
    
    __tablename__ = "business_rules"
    
    rule_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Unique key for lookup (e.g., "overtime_daily_threshold")
    rule_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Value stored as string, parsed by application
    rule_value: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Human-readable description of what this rule does
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Data type hint for the UI (string, integer, decimal, boolean, choice)
    value_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="string"
    )
    
    # For 'choice' type, comma-separated list of valid options
    valid_options: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Audit fields
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    modified_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False
    )
    
    # Relationship
    modifier: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[modified_by]
    )
    
    def __repr__(self) -> str:
        return f"<BusinessRule {self.rule_key}={self.rule_value}>"
    
    def get_int(self) -> int:
        """Parse value as integer."""
        return int(self.rule_value)
    
    def get_float(self) -> float:
        """Parse value as float."""
        return float(self.rule_value)
    
    def get_bool(self) -> bool:
        """Parse value as boolean."""
        return self.rule_value.lower() in ("true", "1", "yes", "on")


# Default business rules to seed on initial setup
DEFAULT_BUSINESS_RULES = [
    {
        "rule_key": "standard_work_week_hours",
        "rule_value": "40",
        "description": "Standard number of hours in a work week",
        "value_type": "integer"
    },
    {
        "rule_key": "overtime_daily_threshold",
        "rule_value": "8",
        "description": "Hours per day before overtime kicks in (0 to disable daily OT)",
        "value_type": "integer"
    },
    {
        "rule_key": "overtime_weekly_threshold",
        "rule_value": "40",
        "description": "Hours per week before overtime kicks in",
        "value_type": "integer"
    },
    {
        "rule_key": "pay_period_type",
        "rule_value": "biweekly",
        "description": "Pay period frequency",
        "value_type": "choice",
        "valid_options": "weekly,biweekly,semimonthly,monthly"
    },
    {
        "rule_key": "week_start_day",
        "rule_value": "sunday",
        "description": "First day of the work week (for overtime calculations)",
        "value_type": "choice",
        "valid_options": "sunday,monday,saturday"
    },
    {
        "rule_key": "max_hours_per_day",
        "rule_value": "24",
        "description": "Maximum hours that can be entered for a single day",
        "value_type": "integer"
    },
    {
        "rule_key": "allow_future_entries",
        "rule_value": "false",
        "description": "Whether employees can enter time for future dates",
        "value_type": "boolean"
    },
    {
        "rule_key": "entry_lookback_days",
        "rule_value": "14",
        "description": "How many days back employees can create/edit entries (0 for unlimited)",
        "value_type": "integer"
    },
]
