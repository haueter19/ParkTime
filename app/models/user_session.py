# ParkTime - User Session Model
# Database-backed session storage for authentication

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employee import Employee


class UserSession(Base):
    """
    Database-backed user sessions.
    
    Storing sessions in the database (rather than just signed cookies) allows:
        - Easy session invalidation (logout, forced logout)
        - Audit trail of login/logout activity
        - Admin visibility into active sessions
        - Session limits per user if needed
    
    The session_token is stored as a hash in production for extra security,
    but for simplicity we're storing it directly here.
    """
    
    __tablename__ = "user_sessions"
    
    __table_args__ = (
        Index("ix_user_sessions_token", "session_token"),
        Index("ix_user_sessions_employee_active", "employee_id", "is_active"),
    )
    
    session_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False,
        index=True
    )
    
    # The session token (stored in cookie)
    session_token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False
    )
    
    # When does this session expire?
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )
    
    # Is this session still valid?
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    logged_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Optional metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Relationship
    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_id]
    )
    
    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<UserSession {self.session_id} ({status}) for employee {self.employee_id}>"
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if session is valid (active and not expired)."""
        return self.is_active and not self.is_expired
