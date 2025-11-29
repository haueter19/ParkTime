# ParkTime - Audit Service
# Centralized service for logging all data changes

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, TypeVar, Type

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect

from app.models.audit_log import AuditLog, create_audit_entry
from app.models.base import Base

# Generic type for SQLAlchemy models
T = TypeVar("T", bound=Base)


class AuditService:
    """
    Service for creating audit log entries.
    
    Usage:
        audit = AuditService(db_session, current_user_id, client_ip)
        
        # For inserts - call after flush to get the ID
        db.add(new_entry)
        db.flush()
        audit.log_insert(new_entry)
        
        # For updates - capture old values before modifying
        old_values = audit.capture_state(entry)
        entry.hours = 8.0
        audit.log_update(entry, old_values)
        
        # For deletes (soft delete)
        audit.log_delete(entry)
        entry.soft_delete(current_user_id)
    
    The service handles JSON serialization of model fields, including
    special handling for dates, decimals, and other non-JSON-native types.
    """
    
    # Tables that should be audited
    AUDITED_TABLES = {
        "time_entries",
        "employees",
        "work_codes",
        "business_rules",
    }
    
    # Fields to exclude from audit snapshots (sensitive or redundant)
    EXCLUDED_FIELDS = {
        "password_hash",  # Never log passwords
    }
    
    def __init__(
        self,
        db: Session,
        performed_by: int,
        ip_address: Optional[str] = None,
        context: Optional[str] = None,
    ):
        """
        Initialize the audit service.
        
        Args:
            db: SQLAlchemy session
            performed_by: employee_id of the user making changes
            ip_address: Client IP address (from request)
            context: Optional context string (e.g., "bulk import", "api")
        """
        self.db = db
        self.performed_by = performed_by
        self.ip_address = ip_address
        self.context = context
    
    def _serialize_value(self, value: Any) -> Any:
        """
        Convert a value to a JSON-serializable format.
        
        Handles dates, decimals, and other special types.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float, str, bool)):
            return value
        # For relationships or complex objects, just store the repr
        return str(value)
    
    def _get_primary_key(self, instance: Base) -> int:
        """Get the primary key value from a model instance."""
        mapper = inspect(type(instance))
        pk_columns = mapper.primary_key
        if len(pk_columns) == 1:
            return getattr(instance, pk_columns[0].name)
        # Composite key - just use first column (shouldn't happen in our schema)
        return getattr(instance, pk_columns[0].name)
    
    def _get_table_name(self, instance: Base) -> str:
        """Get the table name from a model instance."""
        return instance.__tablename__
    
    def capture_state(self, instance: Base) -> dict[str, Any]:
        """
        Capture the current state of a model instance as a dict.
        
        Call this BEFORE making changes to capture the "old" state.
        
        Args:
            instance: SQLAlchemy model instance
            
        Returns:
            Dict of {column_name: value} for all columns
        """
        mapper = inspect(type(instance))
        state = {}
        
        for column in mapper.columns:
            if column.name in self.EXCLUDED_FIELDS:
                continue
            value = getattr(instance, column.name)
            state[column.name] = self._serialize_value(value)
        
        return state
    
    def _diff_states(
        self,
        old_state: dict[str, Any],
        new_state: dict[str, Any]
    ) -> list[str]:
        """
        Compare two states and return list of changed field names.
        """
        changed = []
        all_keys = set(old_state.keys()) | set(new_state.keys())
        
        for key in all_keys:
            old_val = old_state.get(key)
            new_val = new_state.get(key)
            if old_val != new_val:
                changed.append(key)
        
        return changed
    
    def log_insert(
        self,
        instance: Base,
        context: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log an INSERT operation.
        
        Call this AFTER adding and flushing the instance (so it has an ID).
        
        Args:
            instance: The newly created model instance
            context: Optional override for the audit context
            
        Returns:
            AuditLog entry (already added to session)
        """
        table_name = self._get_table_name(instance)
        
        if table_name not in self.AUDITED_TABLES:
            return None
        
        new_values = self.capture_state(instance)
        record_id = self._get_primary_key(instance)
        
        entry = create_audit_entry(
            table_name=table_name,
            record_id=record_id,
            action="INSERT",
            performed_by=self.performed_by,
            new_values=new_values,
            ip_address=self.ip_address,
            context=context or self.context,
        )
        
        self.db.add(entry)
        return entry
    
    def log_update(
        self,
        instance: Base,
        old_state: dict[str, Any],
        context: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log an UPDATE operation.
        
        Args:
            instance: The modified model instance
            old_state: State captured before modifications (from capture_state)
            context: Optional override for the audit context
            
        Returns:
            AuditLog entry (already added to session), or None if no changes
        """
        table_name = self._get_table_name(instance)
        
        if table_name not in self.AUDITED_TABLES:
            return None
        
        new_state = self.capture_state(instance)
        changed_fields = self._diff_states(old_state, new_state)
        
        # Don't log if nothing actually changed
        if not changed_fields:
            return None
        
        record_id = self._get_primary_key(instance)
        
        entry = create_audit_entry(
            table_name=table_name,
            record_id=record_id,
            action="UPDATE",
            performed_by=self.performed_by,
            old_values=old_state,
            new_values=new_state,
            changed_fields=changed_fields,
            ip_address=self.ip_address,
            context=context or self.context,
        )
        
        self.db.add(entry)
        return entry
    
    def log_delete(
        self,
        instance: Base,
        context: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log a DELETE operation.
        
        For soft deletes, call this BEFORE setting is_deleted=True
        so the captured state shows the record as it was.
        
        Args:
            instance: The model instance being deleted
            context: Optional override for the audit context
            
        Returns:
            AuditLog entry (already added to session)
        """
        table_name = self._get_table_name(instance)
        
        if table_name not in self.AUDITED_TABLES:
            return None
        
        old_values = self.capture_state(instance)
        record_id = self._get_primary_key(instance)
        
        entry = create_audit_entry(
            table_name=table_name,
            record_id=record_id,
            action="DELETE",
            performed_by=self.performed_by,
            old_values=old_values,
            ip_address=self.ip_address,
            context=context or self.context,
        )
        
        self.db.add(entry)
        return entry
    
    def log_restore(
        self,
        instance: Base,
        context: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log a RESTORE operation (un-deleting a soft-deleted record).
        
        Args:
            instance: The model instance being restored
            context: Optional override for the audit context
            
        Returns:
            AuditLog entry (already added to session)
        """
        table_name = self._get_table_name(instance)
        
        if table_name not in self.AUDITED_TABLES:
            return None
        
        new_values = self.capture_state(instance)
        record_id = self._get_primary_key(instance)
        
        entry = create_audit_entry(
            table_name=table_name,
            record_id=record_id,
            action="RESTORE",
            performed_by=self.performed_by,
            new_values=new_values,
            ip_address=self.ip_address,
            context=context or self.context,
        )
        
        self.db.add(entry)
        return entry


class AuditQuery:
    """
    Helper class for querying audit logs.
    
    Usage:
        query = AuditQuery(db)
        
        # Get history for a specific record
        history = query.get_record_history("time_entries", 42)
        
        # Get all changes by a user
        changes = query.get_changes_by_user(employee_id=5, limit=100)
        
        # Get recent changes across all tables
        recent = query.get_recent_changes(hours=24)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_record_history(
        self,
        table_name: str,
        record_id: int,
    ) -> list[AuditLog]:
        """
        Get the full audit history for a specific record.
        
        Returns entries in chronological order (oldest first).
        """
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.table_name == table_name,
                AuditLog.record_id == record_id,
            )
            .order_by(AuditLog.performed_at.asc())
            .all()
        )
    
    def get_changes_by_user(
        self,
        employee_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get all changes made by a specific user.
        
        Returns entries in reverse chronological order (newest first).
        """
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.performed_by == employee_id)
            .order_by(AuditLog.performed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
    
    def get_recent_changes(
        self,
        hours: int = 24,
        table_name: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Get recent changes across all tables.
        
        Args:
            hours: How far back to look
            table_name: Filter to specific table (optional)
            action: Filter to specific action type (optional)
            limit: Maximum records to return
            
        Returns entries in reverse chronological order.
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = (
            self.db.query(AuditLog)
            .filter(AuditLog.performed_at >= cutoff)
        )
        
        if table_name:
            query = query.filter(AuditLog.table_name == table_name)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        return (
            query
            .order_by(AuditLog.performed_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_changes_in_date_range(
        self,
        start_date: date,
        end_date: date,
        table_name: Optional[str] = None,
    ) -> list[AuditLog]:
        """
        Get all changes within a date range.
        
        Useful for compliance reports ("show all changes in pay period").
        """
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        query = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.performed_at >= start_datetime,
                AuditLog.performed_at <= end_datetime,
            )
        )
        
        if table_name:
            query = query.filter(AuditLog.table_name == table_name)
        
        return query.order_by(AuditLog.performed_at.asc()).all()
