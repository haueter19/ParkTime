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
    Employee model for authentication and authorization.
    
    Roles:
        - 'employee': Can manage their own time entries
        - 'manager': Can manage their own + their direct reports' entries
        - 'admin': Full system access
    
    The role hierarchy is:
        employee < manager < admin
    
    Managers have a hierarchical relationship (manager_id references another employee).
    This enables org chart functionality and permission checks.
    """
    
    __tablename__ = "employees"
    
    employee_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Authentication
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True  # Nullable for initial setup
    )
    
    # Personal info
    first_name: Mapped[str] = mapped_column(
        String(75),
        nullable=False
    )
    
    last_name: Mapped[str] = mapped_column(
        String(75),
        nullable=False
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Authorization
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="employee"
    )
    
    # Organizational hierarchy
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True,
        index=True
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=True
    )
    
    # Relationships
    time_entries: Mapped[List["TimeEntry"]] = relationship(
        "TimeEntry",
        back_populates="employee",
        foreign_keys="TimeEntry.employee_id"
    )
    
    # Manager relationship (self-referential)
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        remote_side=[employee_id],
        foreign_keys=[manager_id],
        back_populates="direct_reports"
    )
    
    direct_reports: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="manager",
        foreign_keys=[manager_id]
    )
    
    def __repr__(self) -> str:
        return f"<Employee {self.username} ({self.role})>"
    
    @property
    def display_name(self) -> str:
        """Full name for display."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == "admin"
    
    @property
    def is_manager(self) -> bool:
        """Check if user is a manager or admin."""
        return self.role in ("manager", "admin")
    
    def can_view_employee(self, employee_id: int) -> bool:
        """
        Check if this user can view/edit time for another employee.
        
        Rules:
            - Admins can view anyone
            - Managers can view their direct reports
            - Employees can only view themselves
        
        Args:
            employee_id: The target employee's ID
            
        Returns:
            True if user has permission
        """
        if self.is_admin:
            return True
        
        if self.employee_id == employee_id:
            return True
        
        if self.is_manager:
            # Check if employee_id is in direct reports
            return any(r.employee_id == employee_id for r in self.direct_reports)
        
        return False