# ParkTime - Time Entry Model

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Boolean, Integer, DateTime, Date, 
    Numeric, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employee import Employee
    from .work_code import WorkCode


class TimeEntry(Base):
    """
    Individual time entry record.
    
    Each entry represents hours worked (or leave taken) for a single 
    employee on a single day with a single work code.
    
    An employee might have multiple entries per day (e.g., 6 hours REG + 2 hours OT).
    
    Soft Delete:
        Entries are never hard-deleted. The is_deleted flag is set to True,
        and the deletion is recorded in the audit_log. This preserves the
        audit trail while hiding deleted entries from normal views.
    """
    
    __tablename__ = "time_entries"
    
    # Composite index for common query pattern: entries for employee in date range
    __table_args__ = (
        Index("ix_time_entries_employee_date", "employee_id", "entry_date"),
        Index("ix_time_entries_date", "entry_date"),
    )
    
    entry_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Whose time is this?
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False,
        index=True
    )
    
    # What type of time?
    work_code_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("work_codes.work_code_id"),
        nullable=False,
        index=True
    )
    
    # When?
    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    
    # How many hours? Using Decimal for precision (e.g., 7.5 hours)
    # Precision 4,2 allows 0.00 to 99.99 hours
    hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False
    )
    
    # Optional notes (project name, description of work, etc.)
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Soft delete flag
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    
    # Audit fields - who created/modified this entry
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Who entered this record (may differ from employee_id if manager enters for employee)
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False
    )
    
    modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=datetime.utcnow
    )
    
    modified_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True
    )
    
    # When was it deleted (if is_deleted=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    deleted_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True
    )
    
    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="time_entries",
        foreign_keys=[employee_id]
    )
    
    work_code: Mapped["WorkCode"] = relationship(
        "WorkCode",
        back_populates="time_entries"
    )
    
    creator: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[created_by]
    )
    
    modifier: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[modified_by]
    )
    
    deleter: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[deleted_by]
    )
    
    def __repr__(self) -> str:
        status = " [DELETED]" if self.is_deleted else ""
        return f"<TimeEntry {self.entry_date} {self.hours}h {self.work_code_id}{status}>"
    
    def soft_delete(self, deleted_by_id: int) -> None:
        """Mark this entry as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_id
    
    def restore(self) -> None:
        """Restore a soft-deleted entry."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
