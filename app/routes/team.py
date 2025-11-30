# ParkTime - Team Management Routes
# Managers viewing and managing their direct reports' time entries

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
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
            .where(Employee.employee_id != user.employee_id)  # Exclude self
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
            .where(Employee.employee_id != user.employee_id)
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