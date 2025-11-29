# ParkTime - Audit Log Model

from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
import json

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employee import Employee


class AuditLog(Base):
    """
    Comprehensive audit log for tracking all data changes.
    
    Every INSERT, UPDATE, and DELETE operation on audited tables
    should create a record here. This provides:
        - Compliance trail for municipal record-keeping
        - Ability to investigate discrepancies
        - Potential for undo/restore functionality
    
    The old_values and new_values fields store JSON representations
    of the record state, enabling full reconstruction of history.
    
    Actions:
        - INSERT: new_values contains the created record
        - UPDATE: old_values and new_values show before/after
        - DELETE: old_values contains the deleted record
        - RESTORE: For soft-delete restorations
    """
    
    __tablename__ = "audit_log"
    
    audit_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Which table was affected
    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    # Primary key of the affected record
    record_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    # What happened: INSERT, UPDATE, DELETE, RESTORE
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    
    # Which fields were changed (for UPDATE), comma-separated
    changed_fields: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # JSON blob of previous state (for UPDATE and DELETE)
    old_values: Mapped[Optional[str]] = mapped_column(
        Text,  # nvarchar(max) on SQL Server
        nullable=True
    )
    
    # JSON blob of new state (for INSERT and UPDATE)
    new_values: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Who made the change
    performed_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.employee_id"),
        nullable=False,
        index=True
    )
    
    # When did it happen (UTC)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Optional: client IP address for additional forensics
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Supports IPv6
        nullable=True
    )
    
    # Optional: additional context (e.g., "bulk import", "manager override")
    context: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Relationship
    performer: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[performed_by]
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.table_name}:{self.record_id} by {self.performed_by}>"
    
    def get_old_values(self) -> Optional[dict]:
        """Parse old_values JSON."""
        if self.old_values:
            return json.loads(self.old_values)
        return None
    
    def get_new_values(self) -> Optional[dict]:
        """Parse new_values JSON."""
        if self.new_values:
            return json.loads(self.new_values)
        return None
    
    def get_changes(self) -> dict[str, tuple[Any, Any]]:
        """
        Return a dict of {field_name: (old_value, new_value)} for changed fields.
        Only meaningful for UPDATE actions.
        """
        if self.action != "UPDATE":
            return {}
        
        old = self.get_old_values() or {}
        new = self.get_new_values() or {}
        
        changes = {}
        for field in (self.changed_fields or "").split(","):
            field = field.strip()
            if field:
                changes[field] = (old.get(field), new.get(field))
        
        return changes


# Helper function to create audit log entries
def create_audit_entry(
    table_name: str,
    record_id: int,
    action: str,
    performed_by: int,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    changed_fields: Optional[list[str]] = None,
    ip_address: Optional[str] = None,
    context: Optional[str] = None,
) -> AuditLog:
    """
    Factory function to create an AuditLog entry.
    
    Args:
        table_name: Name of the affected table
        record_id: Primary key of the affected record
        action: INSERT, UPDATE, DELETE, or RESTORE
        performed_by: employee_id of who made the change
        old_values: Dict of previous values (for UPDATE/DELETE)
        new_values: Dict of new values (for INSERT/UPDATE)
        changed_fields: List of field names that changed (for UPDATE)
        ip_address: Client IP address
        context: Additional context string
    
    Returns:
        AuditLog instance (not yet added to session)
    """
    return AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        performed_by=performed_by,
        old_values=json.dumps(old_values) if old_values else None,
        new_values=json.dumps(new_values) if new_values else None,
        changed_fields=",".join(changed_fields) if changed_fields else None,
        ip_address=ip_address,
        context=context,
    )
