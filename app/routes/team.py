# ParkTime - Team Management Routes
# Managers viewing and managing their direct reports' time entries

from datetime import date, datetime, timedelta
from datetime import time as time_type
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_manager
from app.models.employee import Employee
from app.models.time_entry import TimeEntry
from app.models.work_code import WorkCode


router = APIRouter(prefix="/team", tags=["team"])


def get_week_bounds(target_date: date) -> tuple[date, date]:
    """Get Monday and Sunday of the week containing target_date."""
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@router.get("", response_class=HTMLResponse)
def team_overview(
    request: Request,
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
    week_of: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    employee_id: Optional[int] = Query(None, description="Filter by specific employee"),
):
    """
    Team time entries overview.
    
    Shows time entries for all direct reports, with optional filtering
    by employee and week.
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
    
    # Get direct reports (or all employees if admin)
    if user.is_admin:
        team_members = db.execute(
            select(Employee)
            .where(Employee.is_active == True)
            .where(Employee.manager_id == user.employee_id)
            .order_by(Employee.last_name, Employee.first_name)
        ).scalars().all()
    else:
        team_members = user.direct_reports
    
    # Filter by specific employee if requested
    if employee_id:
        team_members = [m for m in team_members if m.employee_id == employee_id]
    
    # Fetch entries for the week for all team members
    team_member_ids = [m.employee_id for m in team_members]
    
    entries = []
    if team_member_ids:
        entries = db.execute(
            select(TimeEntry)
            .where(
                TimeEntry.employee_id.in_(team_member_ids),
                TimeEntry.is_deleted == False,
                TimeEntry.entry_date >= week_start,
                TimeEntry.entry_date <= week_end,
            )
            .order_by(TimeEntry.employee_id, TimeEntry.entry_date, TimeEntry.entry_id)
        ).scalars().all()
    
    # Group entries by employee and date
    entries_by_employee = {}
    for entry in entries:
        if entry.employee_id not in entries_by_employee:
            entries_by_employee[entry.employee_id] = {}
        if entry.entry_date not in entries_by_employee[entry.employee_id]:
            entries_by_employee[entry.employee_id][entry.entry_date] = []
        entries_by_employee[entry.employee_id][entry.entry_date].append(entry)
    
    # Calculate totals per employee
    employee_totals = {}
    for emp_id, dates in entries_by_employee.items():
        total = sum(
            sum(e.hours for e in date_entries)
            for date_entries in dates.values()
        )
        employee_totals[emp_id] = total
    
    # Overall team total
    team_total = sum(employee_totals.values())
    
    # Generate list of dates for the week
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # Navigation dates
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    
    return templates.TemplateResponse(
        "team/overview.html",
        {
            "request": request,
            "user": user,
            "team_members": team_members,
            "entries_by_employee": entries_by_employee,
            "employee_totals": employee_totals,
            "team_total": team_total,
            "week_dates": week_dates,
            "week_start": week_start,
            "week_end": week_end,
            "prev_week": prev_week,
            "next_week": next_week,
            "today": date.today(),
            "selected_employee_id": employee_id,
        },
    )


@router.get("/employee/{employee_id}", response_class=HTMLResponse)
def team_member_detail(
    request: Request,
    employee_id: int,
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
    week_of: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
):
    """
    Detailed view of a single team member's time entries.
    
    Similar to the employee's own view, but for managers.
    """
    templates = request.app.state.templates
    
    # Get the team member
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check permission
    if not user.can_view_employee(employee_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    
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
            TimeEntry.employee_id == employee_id,
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
        "team/employee_detail.html",
        {
            "request": request,
            "user": user,
            "employee": employee,
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


@router.get("/summary", response_class=HTMLResponse)
def team_summary(
    request: Request,
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Team summary report showing totals by employee and work code.
    
    Useful for payroll preparation and oversight.
    """
    templates = request.app.state.templates
    
    # Default to current pay period (last 2 weeks)
    if not start_date or not end_date:
        end = date.today()
        start = end - timedelta(days=13)  # 2 weeks
    else:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            end = date.today()
            start = end - timedelta(days=13)
    
    # Get direct reports (or all employees if admin)
    if user.is_admin:
        team_members = db.execute(
            select(Employee)
            .where(Employee.is_active == True)
            .where(Employee.manager_id == user.employee_id)
            .order_by(Employee.last_name, Employee.first_name)
        ).scalars().all()
    else:
        team_members = user.direct_reports
    
    team_member_ids = [m.employee_id for m in team_members]
    
    # Fetch all entries in date range
    entries = []
    if team_member_ids:
        entries = db.execute(
            select(TimeEntry)
            .where(
                TimeEntry.employee_id.in_(team_member_ids),
                TimeEntry.is_deleted == False,
                TimeEntry.entry_date >= start,
                TimeEntry.entry_date <= end,
            )
            .order_by(TimeEntry.employee_id)
        ).scalars().all()
    
    # Build summary data: employee -> work_code -> total hours
    summary = {}
    for entry in entries:
        if entry.employee_id not in summary:
            summary[entry.employee_id] = {
                'employee': entry.employee,
                'by_code': {},
                'total': Decimal('0.00'),
            }
        
        code_key = entry.work_code.code
        if code_key not in summary[entry.employee_id]['by_code']:
            summary[entry.employee_id]['by_code'][code_key] = {
                'work_code': entry.work_code,
                'hours': Decimal('0.00'),
            }
        
        summary[entry.employee_id]['by_code'][code_key]['hours'] += entry.hours
        summary[entry.employee_id]['total'] += entry.hours
    
    # Get all unique work codes used
    all_codes = set()
    for emp_data in summary.values():
        all_codes.update(emp_data['by_code'].keys())
    all_codes = sorted(all_codes)
    
    # Grand totals
    grand_total = sum(emp_data['total'] for emp_data in summary.values())
    code_totals = {code: Decimal('0.00') for code in all_codes}
    for emp_data in summary.values():
        for code, data in emp_data['by_code'].items():
            code_totals[code] += data['hours']
    
    return templates.TemplateResponse(
        "team/summary.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
            "all_codes": all_codes,
            "code_totals": code_totals,
            "grand_total": grand_total,
            "start_date": start,
            "end_date": end,
            "team_members": team_members,
        },
    )


@router.get("/employee/{employee_id}/entry/new", response_class=HTMLResponse)
def new_team_entry_form(
    request: Request,
    employee_id: int,
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
    entry_date: Optional[str] = Query(None),
):
    """Display form for creating a time entry for a team member."""
    templates = request.app.state.templates
    
    # Get the team member
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check permission
    if not user.can_view_employee(employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get work codes
    work_codes = db.execute(
        select(WorkCode)
        .where(WorkCode.is_active == True)
        .order_by(WorkCode.sort_order, WorkCode.code)
    ).scalars().all()
    
    # Default to today if no date specified
    if entry_date:
        try:
            default_date = date.fromisoformat(entry_date)
        except ValueError:
            default_date = date.today()
    else:
        default_date = date.today()
    
    return templates.TemplateResponse(
        "team/entry_form.html",
        {
            "request": request,
            "user": user,
            "employee": employee,
            "work_codes": work_codes,
            "entry": None,
            "default_date": default_date,
            "form_action": f"/team/employee/{employee_id}/entry",
        },
    )


@router.post("/employee/{employee_id}/entry", response_class=HTMLResponse)
def create_team_entry(
    request: Request,
    employee_id: int,
    entry_date: str = Form(...),
    work_code_id: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    notes: Optional[str] = Form(None),
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Create a time entry for a team member."""
    templates = request.app.state.templates
    
    # Get the team member
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check permission
    if not user.can_view_employee(employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    errors = []
    
    # Validate date
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = date.today()
    
    # Parse times (HH:MM)
    try:
        st = time_type.fromisoformat(start_time)
        et = time_type.fromisoformat(end_time)
        parsed_start = datetime.combine(parsed_date, st)
        parsed_end = datetime.combine(parsed_date, et)
        if parsed_end <= parsed_start:
            errors.append("End time must be after start time")
    except Exception:
        errors.append("Invalid time format")
        parsed_start = None
        parsed_end = None
    
    if errors:
        work_codes = db.execute(
            select(WorkCode)
            .where(WorkCode.is_active == True)
            .order_by(WorkCode.sort_order, WorkCode.code)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "team/entry_form.html",
            {
                "request": request,
                "user": user,
                "employee": employee,
                "work_codes": work_codes,
                "entry": None,
                "default_date": parsed_date,
                "form_action": f"/team/employee/{employee_id}/entry",
                "errors": errors,
                "form_data": {
                    "work_code_id": work_code_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "notes": notes,
                },
            },
            status_code=400,
        )
    
    # Create the entry
    from app.services.time_entry import TimeEntryService
    
    service = TimeEntryService(
        db, 
        user.employee_id,  # Manager is creating this
        request.client.host if request.client else None,
    )
    
    try:
        entry = service.create_entry(
            employee_id=employee_id,  # Entry is FOR the team member
            work_code_id=work_code_id,
            start_time=parsed_start,
            end_time=parsed_end,
            notes=notes.strip() if notes else None,
        )
        db.commit()
        
        # Redirect to team member's detail page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/team/employee/{employee_id}?week_of={parsed_date.isoformat()}",
            status_code=302,
        )
    
    except ValueError as e:
        errors.append(str(e))
        work_codes = db.execute(
            select(WorkCode)
            .where(WorkCode.is_active == True)
            .order_by(WorkCode.sort_order, WorkCode.code)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "team/entry_form.html",
            {
                "request": request,
                "user": user,
                "employee": employee,
                "work_codes": work_codes,
                "entry": None,
                "default_date": parsed_date,
                "form_action": f"/team/employee/{employee_id}/entry",
                "errors": errors,
            },
            status_code=400,
        )
    

@router.get("/employee/{employee_id}/entry/inline/new", response_class=HTMLResponse)
def inline_new_team_entry_form(
    request: Request,
    employee_id: int,
    entry_date: str = Query(...),
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Return inline form for adding entry to a specific date for a team member."""
    templates = request.app.state.templates
    
    # Get the team member
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check permission
    if not user.can_view_employee(employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get work codes
    work_codes = db.execute(
        select(WorkCode)
        .where(WorkCode.is_active == True)
        .order_by(WorkCode.sort_order, WorkCode.code)
    ).scalars().all()
    
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        parsed_date = date.today()
    
    return templates.TemplateResponse(
        "team/_entry_row_new.html",
        {
            "request": request,
            "user": user,
            "employee_id": employee_id,
            "work_codes": work_codes,
            "entry_date": parsed_date,
        },
    )


@router.post("/employee/{employee_id}/entry/inline", response_class=HTMLResponse)
def create_team_entry_inline(
    request: Request,
    employee_id: int,
    entry_date: str = Form(...),
    work_code_id: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    notes: Optional[str] = Form(None),
    user: Employee = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Create a time entry inline for a team member (HTMX endpoint)."""
    templates = request.app.state.templates
    
    # Get the team member
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check permission
    if not user.can_view_employee(employee_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    errors = []
    
    # Validate date
    try:
        parsed_date = date.fromisoformat(entry_date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = date.today()
    
    # Parse times (HH:MM)
    parsed_start = None
    parsed_end = None
    try:
        st = time_type.fromisoformat(start_time)
        et = time_type.fromisoformat(end_time)
        parsed_start = datetime.combine(parsed_date, st)
        parsed_end = datetime.combine(parsed_date, et)
        if parsed_end <= parsed_start:
            errors.append("End time must be after start time")
    except Exception:
        errors.append("Invalid time format")
    
    if errors or not parsed_start or not parsed_end:
        # Return form with errors
        work_codes = db.execute(
            select(WorkCode)
            .where(WorkCode.is_active == True)
            .order_by(WorkCode.sort_order, WorkCode.code)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "team/_entry_row_new.html",
            {
                "request": request,
                "user": user,
                "employee_id": employee_id,
                "work_codes": work_codes,
                "entry_date": parsed_date,
                "errors": errors,
                "form_data": {
                    "work_code_id": work_code_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "notes": notes,
                },
            },
            status_code=400,
        )
    
    # Create the entry
    from app.services.time_entry import TimeEntryService
    
    service = TimeEntryService(
        db, 
        user.employee_id,  # Manager is creating this
        request.client.host if request.client else None,
    )
    
    try:
        entry = service.create_entry(
            employee_id=employee_id,  # Entry is FOR the team member
            work_code_id=work_code_id,
            start_time=parsed_start,
            end_time=parsed_end,
            notes=notes.strip() if notes else None,
        )
        db.commit()
        
        # Refresh to get relationships
        db.refresh(entry)
        
        # Return the new entry row
        return templates.TemplateResponse(
            "team/_entry_row.html",
            {
                "request": request,
                "entry": entry,
                "user": user,
                "employee": employee,
            },
            headers={"HX-Trigger": "teamEntryCreated"},
        )
    
    except ValueError as e:
        errors.append(str(e))
        work_codes = db.execute(
            select(WorkCode)
            .where(WorkCode.is_active == True)
            .order_by(WorkCode.sort_order, WorkCode.code)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "team/_entry_row_new.html",
            {
                "request": request,
                "user": user,
                "employee_id": employee_id,
                "work_codes": work_codes,
                "entry_date": parsed_date,
                "errors": errors,
            },
            status_code=400,
        )




