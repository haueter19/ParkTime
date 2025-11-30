# ParkTime - Time Entry Service
# Business logic for time entry CRUD with audit logging

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_entry import TimeEntry
from app.models.employee import Employee
from app.models.work_code import WorkCode
from app.services.audit import AuditService


class TimeEntryService:
    """
    Service for managing time entries with built-in audit logging.
    
    All create/update/delete operations automatically generate audit records.
    
    Usage:
        service = TimeEntryService(db, current_user_id, request.client.host)
        
        # Create with times
        entry = service.create_entry(
            employee_id=5,
            work_code_id=1,
            start_time=datetime(2025, 1, 15, 8, 0),
            end_time=datetime(2025, 1, 15, 16, 0),
            notes="Regular shift"
        )
        
        # Update times
        entry = service.update_entry(
            entry_id=42,
            start_time=datetime(2025, 1, 15, 8, 0),
            end_time=datetime(2025, 1, 15, 16, 30),
            notes="Updated - stayed late"
        )
    """
    
    def __init__(
        self,
        db: Session,
        current_user_id: int,
        ip_address: Optional[str] = None,
    ):
        self.db = db
        self.current_user_id = current_user_id
        self.audit = AuditService(db, current_user_id, ip_address)
    
    def get_entry(self, entry_id: int, include_deleted: bool = False) -> Optional[TimeEntry]:
        """Fetch a single time entry by ID."""
        query = select(TimeEntry).where(TimeEntry.entry_id == entry_id)
        
        if not include_deleted:
            query = query.where(TimeEntry.is_deleted == False)
        
        return self.db.execute(query).scalar_one_or_none()
    
    def create_entry(
        self,
        employee_id: int,
        work_code_id: int,
        start_time: datetime,
        end_time: datetime,
        notes: Optional[str] = None,
    ) -> TimeEntry:
        """
        Create a new time entry with audit logging.
        
        Args:
            employee_id: Whose time this is
            work_code_id: Type of time (REG, OT, SICK, etc.)
            start_time: When work started (full datetime)
            end_time: When work ended (full datetime)
            notes: Optional notes
            
        Returns:
            The created TimeEntry
            
        Raises:
            ValueError: If validation fails
        """
        # Validation
        self._validate_employee_exists(employee_id)
        self._validate_work_code_exists(work_code_id)
        self._validate_times(start_time, end_time)
        
        # Create the entry
        entry = TimeEntry(
            employee_id=employee_id,
            work_code_id=work_code_id,
            notes=notes,
            created_by=self.current_user_id,
        )
        
        # Set times and compute hours
        entry.set_times_and_compute_hours(start_time, end_time)
        
        self.db.add(entry)
        self.db.flush()  # Get the entry_id
        
        # Audit log
        self.audit.log_insert(entry)
        
        return entry
    
    def update_entry(
        self,
        entry_id: int,
        work_code_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> TimeEntry:
        """
        Update an existing time entry with audit logging.
        
        Only provided fields are updated. Pass None to leave unchanged.
        
        Args:
            entry_id: ID of entry to update
            work_code_id: New work code (optional)
            start_time: New start time (optional)
            end_time: New end time (optional)
            notes: New notes (optional, pass empty string to clear)
            
        Returns:
            The updated TimeEntry
            
        Raises:
            ValueError: If entry not found or validation fails
        """
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Time entry {entry_id} not found")
        
        # Capture state BEFORE changes
        old_state = self.audit.capture_state(entry)
        
        # Apply updates
        if work_code_id is not None:
            self._validate_work_code_exists(work_code_id)
            entry.work_code_id = work_code_id
        
        # Handle time updates - if either time changes, both must be provided or we use existing
        new_start = start_time if start_time is not None else entry.start_time
        new_end = end_time if end_time is not None else entry.end_time
        
        if start_time is not None or end_time is not None:
            self._validate_times(new_start, new_end)
            entry.set_times_and_compute_hours(new_start, new_end)
        
        if notes is not None:
            entry.notes = notes if notes else None
        
        # Update audit fields
        entry.modified_at = datetime.utcnow()
        entry.modified_by = self.current_user_id
        
        # Log the update (only if something changed)
        self.audit.log_update(entry, old_state)
        
        return entry
    
    def delete_entry(self, entry_id: int) -> TimeEntry:
        """
        Soft-delete a time entry with audit logging.
        
        The entry is not removed from the database, just marked as deleted.
        
        Args:
            entry_id: ID of entry to delete
            
        Returns:
            The deleted TimeEntry
            
        Raises:
            ValueError: If entry not found
        """
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Time entry {entry_id} not found")
        
        # Log BEFORE applying soft delete
        self.audit.log_delete(entry)
        
        # Soft delete
        entry.soft_delete(self.current_user_id)
        
        return entry
    
    def restore_entry(self, entry_id: int) -> TimeEntry:
        """
        Restore a soft-deleted time entry.
        
        Args:
            entry_id: ID of entry to restore
            
        Returns:
            The restored TimeEntry
            
        Raises:
            ValueError: If entry not found or not deleted
        """
        entry = self.get_entry(entry_id, include_deleted=True)
        if not entry:
            raise ValueError(f"Time entry {entry_id} not found")
        
        if not entry.is_deleted:
            raise ValueError(f"Time entry {entry_id} is not deleted")
        
        # Restore
        entry.restore()
        entry.modified_at = datetime.utcnow()
        entry.modified_by = self.current_user_id
        
        # Log the restore
        self.audit.log_restore(entry)
        
        return entry
    
    # Validation helpers
    
    def _validate_employee_exists(self, employee_id: int) -> None:
        """Verify employee exists and is active."""
        exists = self.db.execute(
            select(Employee.employee_id)
            .where(Employee.employee_id == employee_id)
            .where(Employee.is_active == True)
        ).scalar_one_or_none()
        
        if not exists:
            raise ValueError(f"Employee {employee_id} not found or inactive")
    
    def _validate_work_code_exists(self, work_code_id: int) -> None:
        """Verify work code exists and is active."""
        exists = self.db.execute(
            select(WorkCode.work_code_id)
            .where(WorkCode.work_code_id == work_code_id)
            .where(WorkCode.is_active == True)
        ).scalar_one_or_none()
        
        if not exists:
            raise ValueError(f"Work code {work_code_id} not found or inactive")
    
    def _validate_times(self, start_time: datetime, end_time: datetime) -> None:
        """Validate start and end times are reasonable."""
        if end_time <= start_time:
            raise ValueError("End time must be after start time")
        
        # Calculate duration in hours
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        if duration_hours > 24:
            raise ValueError("Entry duration cannot exceed 24 hours")
        
        if duration_hours < 0.25:  # 15 minutes minimum
            raise ValueError("Entry duration must be at least 15 minutes")