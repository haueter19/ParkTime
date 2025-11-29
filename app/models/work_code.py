# ParkTime - Work Code Model

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .time_entry import TimeEntry
    from .employee import Employee


class WorkCode(Base):
    """
    Work codes for categorizing time entries.
    
    Code Types:
        - 'work': Regular work hours (REG, OT, TRAINING, etc.)
        - 'leave_paid': Paid time off (VAC, SICK, HOLIDAY, etc.)
        - 'leave_unpaid': Unpaid time off (LWOP, SUSPENSION, etc.)
    
    The code_type field enables:
        - Grouping in reports ("total leave hours this quarter")
        - Business rule enforcement ("leave_unpaid doesn't count toward overtime")
        - Payroll categorization
    """
    
    __tablename__ = "work_codes"
    
    work_code_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Short code for display and data entry (e.g., "REG", "OT", "SICK")
    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Human-readable description
    description: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    # Category for grouping and business logic
    code_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="work"
    )
    
    # Display order in dropdowns/lists
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Soft delete - inactive codes won't appear in dropdowns
    # but historical entries retain the reference
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False
    )
    
    # Relationships
    creator: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[created_by]
    )
    
    time_entries: Mapped[List["TimeEntry"]] = relationship(
        "TimeEntry",
        back_populates="work_code"
    )
    
    def __repr__(self) -> str:
        return f"<WorkCode {self.code} ({self.code_type})>"
    
    @property
    def is_leave(self) -> bool:
        """Check if this code represents any type of leave."""
        return self.code_type in ("leave_paid", "leave_unpaid")
    
    @property
    def is_paid(self) -> bool:
        """Check if this code represents paid time (work or paid leave)."""
        return self.code_type in ("work", "leave_paid")


# Default work codes to seed on initial setup
DEFAULT_WORK_CODES = [
    {"code": "REG", "description": "Regular Hours", "code_type": "work", "sort_order": 1},
    {"code": "OT", "description": "Overtime", "code_type": "work", "sort_order": 2},
    {"code": "TRAINING", "description": "Training", "code_type": "work", "sort_order": 3},
    {"code": "VAC", "description": "Vacation", "code_type": "leave_paid", "sort_order": 10},
    {"code": "SICK", "description": "Sick Leave", "code_type": "leave_paid", "sort_order": 11},
    {"code": "PERSONAL", "description": "Personal Day", "code_type": "leave_paid", "sort_order": 12},
    {"code": "HOLIDAY", "description": "Holiday", "code_type": "leave_paid", "sort_order": 13},
    {"code": "JURY", "description": "Jury Duty", "code_type": "leave_paid", "sort_order": 14},
    {"code": "BEREAVEMENT", "description": "Bereavement", "code_type": "leave_paid", "sort_order": 15},
    {"code": "LWOP", "description": "Leave Without Pay", "code_type": "leave_unpaid", "sort_order": 20},
]
