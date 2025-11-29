# ParkTime - Time Entry Routes
# CRUD operations for time entries with HTMX support

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.employee import Employee
from app.models.time_entry import TimeEntry
from app.models.work_code import WorkCode
from app.services.time_entry import TimeEntryService
from app.services.audit import AuditService


router = APIRouter(prefix="/entries", tags=["entries"])


# Helper functions

def get_week_bounds(target_date: date) -> tuple[date, date]:
    """Get Monday and Sunday of the week containing target_date."""
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_work_codes(db: Session) -> list[WorkCode]:
    """Get all active work codes for dropdowns."""
    return db.execute(
        select(WorkCode)
        .where(WorkCode.is_active == True)
        .order_by(WorkCode.sort_order, WorkCode.code)
    ).scalars().all()


# Routes

@router.get("", response_class=HTMLResponse)
def list_entries(
    request: Request,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
    week_of: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
):
    """
    Display time entries for a week.
    
    Defaults to current week. Use week_of parameter to view other weeks.
    """
    templates = request.app.state.templates
    
    # Parse target date
    if week_of:
        try:
            target_date = date.fromisoformat(week_of)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()
    
    # Get week bounds
    week_start, week_end = get_week_bounds(target_date)
    
    # Fetch entries for this week
    entries = db.execute(
        select(TimeEntry)
        .where(
            TimeEntry.employee_id == user.employee_id,
            TimeEntry.is_deleted == False,
            TimeEntry.entry_date >= week_start,
            TimeEntry.entry_date <= week_end,
        )
        .order_by(TimeEntry.entry_date, TimeEntry.entry_id)
    ).scalars().all()
    
    # Group entries by date
    entries_by_date = {}
    for entry in entries:
        if entry.entry_date not in entries_by_date:
            entries_by_date[entry.entry_date] = []
        entries_by_date[entry.entry_date].append(entry)
    
    # Calculate daily and weekly totals
    daily_totals = {d: sum(e.hours for e in entries_by_date.get(d, [])) 
                    for d in entries_by_date}
    weekly_total = sum(daily_totals.values())
    
    # Generate list of dates for the week
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # Navigation dates
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    
    return templates.TemplateResponse(
        "entries/list.html",
        {
            "request": request,
            "user": user,
            "entries_by_date": entries_by_date,
            "daily_totals": daily_totals,
            "weekly_total": weekly_total,
            "week_dates": week_dates,
            "week_start": week_start,
            "week_end": week_end,
            "prev_week": prev_week,
            "next_week": next_week,
            "today": date.today(),
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_entry_form(
    request: Request,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
    entry_date: Optional[str] = Query(None),
):
    """Display form for creating a new time entry."""
    templates = request.app.state.templates
    work_codes = get_work_codes(db)
    
    # Default to today if no date specified
    if entry_date:
        try:
            default_date = date.fromisoformat(entry_date)
        except ValueError:
            default_date = date.today()
    else:
        default_date = date.today()
    
    return templates.TemplateResponse(
        "entries/form.html",
        {
            "request": request,
            "user": user,
            "work_codes": work_codes,
            "entry": None,
            "default_date": default_date,
            "form_action": "/entries",
            "form_method": "post",
        },
    )


@router.post("", response_class=HTMLResponse)
def create_entry(
    request: Request,
    entry_date: str = Form(...),
    work_code_id: int = Form(...),
    hours: str = Form(...),
    notes: Optional[str] = Form(None),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new time entry."""
    templates = request.app.state.templates
    work_codes = get_work_codes(db)
    errors = []
    
    # Validate date
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = date.today()
    
    # Validate hours
    try:
        parsed_hours = Decimal(hours)
        if parsed_hours <= 0:
            errors.append("Hours must be positive")
        if parsed_hours > 24:
            errors.append("Hours cannot exceed 24")
    except InvalidOperation:
        errors.append("Invalid hours value")
        parsed_hours = Decimal("0")
    
    if errors:
        return templates.TemplateResponse(
            "entries/form.html",
            {
                "request": request,
                "user": user,
                "work_codes": work_codes,
                "entry": None,
                "default_date": parsed_date,
                "form_action": "/entries",
                "form_method": "post",
                "errors": errors,
                "form_data": {
                    "work_code_id": work_code_id,
                    "hours": hours,
                    "notes": notes,
                },
            },
            status_code=400,
        )
    
    # Create the entry
    service = TimeEntryService(
        db, 
        user.employee_id,
        request.client.host if request.client else None,
    )
    
    try:
        entry = service.create_entry(
            employee_id=user.employee_id,
            work_code_id=work_code_id,
            entry_date=parsed_date,
            hours=parsed_hours,
            notes=notes.strip() if notes else None,
        )
        db.commit()
        
        # Check if HTMX request
        if request.headers.get("HX-Request"):
            # Return the new row to be inserted into the table
            return templates.TemplateResponse(
                "entries/_row.html",
                {
                    "request": request,
                    "entry": entry,
                    "user": user,
                },
                headers={"HX-Trigger": "entryCreated"},
            )
        else:
            # Full page redirect
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url=f"/entries?week_of={parsed_date.isoformat()}",
                status_code=302,
            )
    
    except ValueError as e:
        errors.append(str(e))
        return templates.TemplateResponse(
            "entries/form.html",
            {
                "request": request,
                "user": user,
                "work_codes": work_codes,
                "entry": None,
                "default_date": parsed_date,
                "form_action": "/entries",
                "form_method": "post",
                "errors": errors,
            },
            status_code=400,
        )


@router.get("/{entry_id}", response_class=HTMLResponse)
def get_entry(
    request: Request,
    entry_id: int,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single entry (returns row partial for HTMX)."""
    templates = request.app.state.templates
    
    entry = db.execute(
        select(TimeEntry)
        .where(TimeEntry.entry_id == entry_id)
        .where(TimeEntry.is_deleted == False)
    ).scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check permission
    if not user.can_view_employee(entry.employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return templates.TemplateResponse(
        "entries/_row.html",
        {
            "request": request,
            "entry": entry,
            "user": user,
        },
    )


@router.get("/{entry_id}/edit", response_class=HTMLResponse)
def edit_entry_form(
    request: Request,
    entry_id: int,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Display inline edit form for an entry (HTMX partial)."""
    templates = request.app.state.templates
    
    entry = db.execute(
        select(TimeEntry)
        .where(TimeEntry.entry_id == entry_id)
        .where(TimeEntry.is_deleted == False)
    ).scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check permission
    if not user.can_view_employee(entry.employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    work_codes = get_work_codes(db)
    
    # For HTMX inline editing, return the edit row
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "entries/_row_edit.html",
            {
                "request": request,
                "entry": entry,
                "work_codes": work_codes,
                "user": user,
            },
        )
    
    # Full page edit form
    return templates.TemplateResponse(
        "entries/form.html",
        {
            "request": request,
            "user": user,
            "work_codes": work_codes,
            "entry": entry,
            "default_date": entry.entry_date,
            "form_action": f"/entries/{entry_id}",
            "form_method": "put",
        },
    )


@router.put("/{entry_id}", response_class=HTMLResponse)
@router.post("/{entry_id}", response_class=HTMLResponse)  # Fallback for forms
def update_entry(
    request: Request,
    entry_id: int,
    entry_date: str = Form(...),
    work_code_id: int = Form(...),
    hours: str = Form(...),
    notes: Optional[str] = Form(None),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing time entry."""
    templates = request.app.state.templates
    
    entry = db.execute(
        select(TimeEntry)
        .where(TimeEntry.entry_id == entry_id)
        .where(TimeEntry.is_deleted == False)
    ).scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check permission
    if not user.can_view_employee(entry.employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    errors = []
    
    # Validate date
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = entry.entry_date
    
    # Validate hours
    try:
        parsed_hours = Decimal(hours)
        if parsed_hours <= 0:
            errors.append("Hours must be positive")
        if parsed_hours > 24:
            errors.append("Hours cannot exceed 24")
    except InvalidOperation:
        errors.append("Invalid hours value")
        parsed_hours = entry.hours
    
    if errors:
        work_codes = get_work_codes(db)
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                "entries/_row_edit.html",
                {
                    "request": request,
                    "entry": entry,
                    "work_codes": work_codes,
                    "user": user,
                    "errors": errors,
                },
                status_code=400,
            )
        else:
            return templates.TemplateResponse(
                "entries/form.html",
                {
                    "request": request,
                    "user": user,
                    "work_codes": work_codes,
                    "entry": entry,
                    "errors": errors,
                },
                status_code=400,
            )
    
    # Update the entry
    service = TimeEntryService(
        db,
        user.employee_id,
        request.client.host if request.client else None,
    )
    
    try:
        updated_entry = service.update_entry(
            entry_id=entry_id,
            entry_date=parsed_date,
            work_code_id=work_code_id,
            hours=parsed_hours,
            notes=notes.strip() if notes else None,
        )
        db.commit()
        
        # Refresh to get updated relationships
        db.refresh(updated_entry)
        
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                "entries/_row.html",
                {
                    "request": request,
                    "entry": updated_entry,
                    "user": user,
                },
                headers={"HX-Trigger": "entryUpdated"},
            )
        else:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url=f"/entries?week_of={parsed_date.isoformat()}",
                status_code=302,
            )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{entry_id}", response_class=HTMLResponse)
def delete_entry(
    request: Request,
    entry_id: int,
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a time entry."""
    entry = db.execute(
        select(TimeEntry)
        .where(TimeEntry.entry_id == entry_id)
        .where(TimeEntry.is_deleted == False)
    ).scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check permission
    if not user.can_view_employee(entry.employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    service = TimeEntryService(
        db,
        user.employee_id,
        request.client.host if request.client else None,
    )
    
    service.delete_entry(entry_id)
    db.commit()
    
    # For HTMX, return empty response to remove the row
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Trigger": "entryDeleted"},
        )
    else:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/entries", status_code=302)


# HTMX partial for adding entry inline
@router.get("/inline/new", response_class=HTMLResponse)
def inline_new_entry_form(
    request: Request,
    entry_date: str = Query(...),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return inline form for adding entry to a specific date."""
    templates = request.app.state.templates
    work_codes = get_work_codes(db)
    
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        parsed_date = date.today()
    
    return templates.TemplateResponse(
        "entries/_row_new.html",
        {
            "request": request,
            "user": user,
            "work_codes": work_codes,
            "entry_date": parsed_date,
        },
    )
