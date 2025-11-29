# ParkTime - Employee Model

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .time_entry import TimeEntry
    from .work_code import WorkCode


class Employee(Base):
    """
    Employee model representing users of the system.
    
    Roles:
        - 'employee': Can view/edit their own time entries
        - 'manager': Can view/edit entries for their direct reports
        - 'admin': Full access to all features and configuration
    """
    
    __tablename__ = "employees"
    
    employee_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Authentication - using network username or email
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Password hash - nullable to support future SSO/Windows auth
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="employee"
    )
    
    # Self-referential FK for manager hierarchy
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True
    )
    
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
    
    # Who created this employee record (nullable for initial admin bootstrap)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True
    )
    
    # Relationships
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        remote_side=[employee_id],
        back_populates="direct_reports",
        foreign_keys=[manager_id]
    )
    
    direct_reports: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="manager",
        foreign_keys=[manager_id]
    )
    
    # Time entries belonging to this employee
    time_entries: Mapped[List["TimeEntry"]] = relationship(
        "TimeEntry",
        back_populates="employee",
        foreign_keys="TimeEntry.employee_id"
    )
    
    def __repr__(self) -> str:
        return f"<Employee {self.username} ({self.display_name})>"
    
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
    
    @property
    def is_manager(self) -> bool:
        return self.role in ("manager", "admin")
    
    def can_view_employee(self, other_employee_id: int) -> bool:
        """Check if this employee can view another employee's time entries."""
        if self.is_admin:
            return True
        if self.employee_id == other_employee_id:
            return True
        if self.is_manager:
            # Check if other employee is a direct report
            return any(r.employee_id == other_employee_id for r in self.direct_reports)
        return False
