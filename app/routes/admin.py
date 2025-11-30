# ParkTime - Admin Routes - COMPLETE CORRECTED VERSION
# Employee management with first_name/last_name and fixed manager_id handling

from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.employee import Employee
from app.models.work_code import WorkCode
from app.models.business_rule import BusinessRule
from app.models.audit_log import AuditLog
from app.models.time_entry import TimeEntry
from app.services.audit import AuditService, AuditQuery
from app.services.auth import AuthService


router = APIRouter(prefix="/admin", tags=["admin"])


# Helper function for parsing optional integers from form data
def parse_optional_int(value: Optional[str]) -> Optional[int]:
    """Convert form string to optional int, handling empty strings."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except (ValueError, AttributeError):
        return None


# =============================================================================
# Employee Management
# =============================================================================

@router.get("/employees", response_class=HTMLResponse)
def list_employees(
    request: Request,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
    show_inactive: bool = Query(False),
):
    """List all employees."""
    templates = request.app.state.templates
    
    query = select(Employee).order_by(Employee.last_name, Employee.first_name)
    if not show_inactive:
        query = query.where(Employee.is_active == True)
    
    employees = db.execute(query).scalars().all()
    
    # Get counts by role
    role_counts = {}
    for emp in employees:
        role_counts[emp.role] = role_counts.get(emp.role, 0) + 1
    
    return templates.TemplateResponse(
        "admin/employees/list.html",
        {
            "request": request,
            "user": user,
            "employees": employees,
            "role_counts": role_counts,
            "show_inactive": show_inactive,
        },
    )


@router.get("/employees/new", response_class=HTMLResponse)
def new_employee_form(
    request: Request,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Display form for creating a new employee."""
    templates = request.app.state.templates
    
    # Get potential managers (active employees who are managers or admins)
    managers = db.execute(
        select(Employee)
        .where(Employee.is_active == True)
        .where(Employee.role.in_(["manager", "admin"]))
        .order_by(Employee.last_name, Employee.first_name)
    ).scalars().all()
    
    return templates.TemplateResponse(
        "admin/employees/form.html",
        {
            "request": request,
            "user": user,
            "employee": None,
            "managers": managers,
            "form_action": "/admin/employees",
        },
    )


@router.post("/employees", response_class=HTMLResponse)
def create_employee(
    request: Request,
    username: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: Optional[str] = Form(None),
    role: str = Form("employee"),
    manager_id: Optional[str] = Form(None),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new employee."""
    templates = request.app.state.templates
    errors = []
    
    # Parse manager_id from string to int
    parsed_manager_id = parse_optional_int(manager_id)
    
    # Validate username uniqueness
    existing = db.execute(
        select(Employee).where(Employee.username == username)
    ).scalar_one_or_none()
    
    if existing:
        errors.append(f"Username '{username}' is already taken")
    
    # Validate role
    if role not in ("employee", "manager", "admin"):
        errors.append("Invalid role")
    
    # Validate names aren't empty
    if not first_name.strip():
        errors.append("First name is required")
    if not last_name.strip():
        errors.append("Last name is required")
    
    if errors:
        managers = db.execute(
            select(Employee)
            .where(Employee.is_active == True)
            .where(Employee.role.in_(["manager", "admin"]))
            .order_by(Employee.last_name, Employee.first_name)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "admin/employees/form.html",
            {
                "request": request,
                "user": user,
                "employee": None,
                "managers": managers,
                "errors": errors,
                "form_data": {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "role": role,
                    "manager_id": parsed_manager_id,
                },
            },
            status_code=400,
        )
    
    # Create employee
    new_employee = Employee(
        username=username.strip().lower(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip() if email else None,
        role=role,
        manager_id=parsed_manager_id,
        is_active=True,
        created_at=datetime.utcnow(),
        created_by=user.employee_id,
    )
    
    db.add(new_employee)
    db.flush()
    
    # Audit log
    audit = AuditService(db, user.employee_id, request.client.host if request.client else None)
    audit.log_insert(new_employee)
    
    db.commit()
    
    return RedirectResponse(url="/admin/employees", status_code=302)


@router.get("/employees/{employee_id}", response_class=HTMLResponse)
def view_employee(
    request: Request,
    employee_id: int,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """View employee details."""
    templates = request.app.state.templates
    
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Get recent time entries
    recent_entries = db.execute(
        select(TimeEntry)
        .where(TimeEntry.employee_id == employee_id)
        .where(TimeEntry.is_deleted == False)
        .order_by(TimeEntry.entry_date.desc())
        .limit(10)
    ).scalars().all()
    
    # Get audit history for this employee
    audit_query = AuditQuery(db)
    audit_history = audit_query.get_record_history("employees", employee_id)
    
    return templates.TemplateResponse(
        "admin/employees/view.html",
        {
            "request": request,
            "user": user,
            "employee": employee,
            "recent_entries": recent_entries,
            "audit_history": audit_history,
        },
    )


@router.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
def edit_employee_form(
    request: Request,
    employee_id: int,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Display form for editing an employee."""
    templates = request.app.state.templates
    
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    managers = db.execute(
        select(Employee)
        .where(Employee.is_active == True)
        .where(Employee.role.in_(["manager", "admin"]))
        .where(Employee.employee_id != employee_id)  # Can't be own manager
        .order_by(Employee.last_name, Employee.first_name)
    ).scalars().all()
    
    return templates.TemplateResponse(
        "admin/employees/form.html",
        {
            "request": request,
            "user": user,
            "employee": employee,
            "managers": managers,
            "form_action": f"/admin/employees/{employee_id}",
        },
    )


@router.post("/employees/{employee_id}", response_class=HTMLResponse)
def update_employee(
    request: Request,
    employee_id: int,
    username: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: Optional[str] = Form(None),
    role: str = Form("employee"),
    manager_id: Optional[str] = Form(None),
    is_active: bool = Form(True),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update an employee."""
    templates = request.app.state.templates
    
    # Parse manager_id from string to int
    parsed_manager_id = parse_optional_int(manager_id)
    
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    errors = []
    
    # Validate username uniqueness (excluding self)
    existing = db.execute(
        select(Employee)
        .where(Employee.username == username)
        .where(Employee.employee_id != employee_id)
    ).scalar_one_or_none()
    
    if existing:
        errors.append(f"Username '{username}' is already taken")
    
    # Validate names aren't empty
    if not first_name.strip():
        errors.append("First name is required")
    if not last_name.strip():
        errors.append("Last name is required")
    
    # Prevent self-demotion from admin
    if employee_id == user.employee_id and role != "admin":
        errors.append("You cannot change your own role from admin")
    
    # Prevent deactivating self
    if employee_id == user.employee_id and not is_active:
        errors.append("You cannot deactivate your own account")
    
    if errors:
        managers = db.execute(
            select(Employee)
            .where(Employee.is_active == True)
            .where(Employee.role.in_(["manager", "admin"]))
            .where(Employee.employee_id != employee_id)
            .order_by(Employee.last_name, Employee.first_name)
        ).scalars().all()
        
        return templates.TemplateResponse(
            "admin/employees/form.html",
            {
                "request": request,
                "user": user,
                "employee": employee,
                "managers": managers,
                "errors": errors,
            },
            status_code=400,
        )
    
    # Capture old state for audit
    audit = AuditService(db, user.employee_id, request.client.host if request.client else None)
    old_state = audit.capture_state(employee)
    
    # Update employee
    employee.username = username.strip().lower()
    employee.first_name = first_name.strip()
    employee.last_name = last_name.strip()
    employee.email = email.strip() if email else None
    employee.role = role
    employee.manager_id = parsed_manager_id
    employee.is_active = is_active
    
    # Audit log
    audit.log_update(employee, old_state)
    
    db.commit()
    
    return RedirectResponse(url="/admin/employees", status_code=302)


@router.post("/employees/{employee_id}/reset-password", response_class=HTMLResponse)
def reset_employee_password(
    request: Request,
    employee_id: int,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reset an employee's password."""
    templates = request.app.state.templates
    
    employee = db.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    ).scalar_one_or_none()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    errors = []
    
    if new_password != confirm_password:
        errors.append("Passwords do not match")
    
    if len(new_password) < 8:
        errors.append("Password must be at least 8 characters")
    
    if errors:
        # Get recent entries and audit history for the view
        recent_entries = db.execute(
            select(TimeEntry)
            .where(TimeEntry.employee_id == employee_id)
            .where(TimeEntry.is_deleted == False)
            .order_by(TimeEntry.entry_date.desc())
            .limit(10)
        ).scalars().all()
        
        audit_query = AuditQuery(db)
        audit_history = audit_query.get_record_history("employees", employee_id)
        
        return templates.TemplateResponse(
            "admin/employees/view.html",
            {
                "request": request,
                "user": user,
                "employee": employee,
                "recent_entries": recent_entries,
                "audit_history": audit_history,
                "password_errors": errors,
            },
            status_code=400,
        )
    
    auth = AuthService(db)
    auth.set_password(employee, new_password)
    
    # Optionally invalidate all sessions
    auth.logout_all_sessions(employee_id)
    
    db.commit()
    
    return RedirectResponse(
        url=f"/admin/employees/{employee_id}?password_reset=success",
        status_code=302,
    )


# =============================================================================
# Work Codes Management
# =============================================================================

@router.get("/work-codes", response_class=HTMLResponse)
def list_work_codes(
    request: Request,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
    show_inactive: bool = Query(False),
):
    """List all work codes."""
    templates = request.app.state.templates
    
    query = select(WorkCode).order_by(WorkCode.sort_order, WorkCode.code)
    if not show_inactive:
        query = query.where(WorkCode.is_active == True)
    
    work_codes = db.execute(query).scalars().all()
    
    # Group by type
    codes_by_type = {}
    for code in work_codes:
        if code.code_type not in codes_by_type:
            codes_by_type[code.code_type] = []
        codes_by_type[code.code_type].append(code)
    
    return templates.TemplateResponse(
        "admin/work_codes/list.html",
        {
            "request": request,
            "user": user,
            "work_codes": work_codes,
            "codes_by_type": codes_by_type,
            "show_inactive": show_inactive,
        },
    )


@router.get("/work-codes/new", response_class=HTMLResponse)
def new_work_code_form(
    request: Request,
    user: Employee = Depends(require_admin),
):
    """Display form for creating a new work code."""
    templates = request.app.state.templates
    
    return templates.TemplateResponse(
        "admin/work_codes/form.html",
        {
            "request": request,
            "user": user,
            "work_code": None,
            "form_action": "/admin/work-codes",
        },
    )


@router.post("/work-codes", response_class=HTMLResponse)
def create_work_code(
    request: Request,
    code: str = Form(...),
    description: str = Form(...),
    code_type: str = Form("work"),
    sort_order: int = Form(0),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new work code."""
    templates = request.app.state.templates
    errors = []
    
    # Normalize code
    code = code.strip().upper()
    
    # Validate uniqueness
    existing = db.execute(
        select(WorkCode).where(WorkCode.code == code)
    ).scalar_one_or_none()
    
    if existing:
        errors.append(f"Code '{code}' already exists")
    
    if code_type not in ("work", "leave_paid", "leave_unpaid"):
        errors.append("Invalid code type")
    
    if errors:
        return templates.TemplateResponse(
            "admin/work_codes/form.html",
            {
                "request": request,
                "user": user,
                "work_code": None,
                "errors": errors,
                "form_data": {
                    "code": code,
                    "description": description,
                    "code_type": code_type,
                    "sort_order": sort_order,
                },
            },
            status_code=400,
        )
    
    new_code = WorkCode(
        code=code,
        description=description.strip(),
        code_type=code_type,
        sort_order=sort_order,
        is_active=True,
        created_at=datetime.utcnow(),
        created_by=user.employee_id,
    )
    
    db.add(new_code)
    db.flush()
    
    audit = AuditService(db, user.employee_id, request.client.host if request.client else None)
    audit.log_insert(new_code)
    
    db.commit()
    
    return RedirectResponse(url="/admin/work-codes", status_code=302)


@router.get("/work-codes/{code_id}/edit", response_class=HTMLResponse)
def edit_work_code_form(
    request: Request,
    code_id: int,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Display form for editing a work code."""
    templates = request.app.state.templates
    
    work_code = db.execute(
        select(WorkCode).where(WorkCode.work_code_id == code_id)
    ).scalar_one_or_none()
    
    if not work_code:
        raise HTTPException(status_code=404, detail="Work code not found")
    
    return templates.TemplateResponse(
        "admin/work_codes/form.html",
        {
            "request": request,
            "user": user,
            "work_code": work_code,
            "form_action": f"/admin/work-codes/{code_id}",
        },
    )


@router.post("/work-codes/{code_id}", response_class=HTMLResponse)
def update_work_code(
    request: Request,
    code_id: int,
    code: str = Form(...),
    description: str = Form(...),
    code_type: str = Form("work"),
    sort_order: int = Form(0),
    is_active: bool = Form(True),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a work code."""
    templates = request.app.state.templates
    
    work_code = db.execute(
        select(WorkCode).where(WorkCode.work_code_id == code_id)
    ).scalar_one_or_none()
    
    if not work_code:
        raise HTTPException(status_code=404, detail="Work code not found")
    
    errors = []
    code = code.strip().upper()
    
    # Validate uniqueness (excluding self)
    existing = db.execute(
        select(WorkCode)
        .where(WorkCode.code == code)
        .where(WorkCode.work_code_id != code_id)
    ).scalar_one_or_none()
    
    if existing:
        errors.append(f"Code '{code}' already exists")
    
    if errors:
        return templates.TemplateResponse(
            "admin/work_codes/form.html",
            {
                "request": request,
                "user": user,
                "work_code": work_code,
                "errors": errors,
            },
            status_code=400,
        )
    
    audit = AuditService(db, user.employee_id, request.client.host if request.client else None)
    old_state = audit.capture_state(work_code)
    
    work_code.code = code
    work_code.description = description.strip()
    work_code.code_type = code_type
    work_code.sort_order = sort_order
    work_code.is_active = is_active
    
    audit.log_update(work_code, old_state)
    db.commit()
    
    return RedirectResponse(url="/admin/work-codes", status_code=302)


# =============================================================================
# Business Rules Management
# =============================================================================

@router.get("/business-rules", response_class=HTMLResponse)
def list_business_rules(
    request: Request,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all business rules."""
    templates = request.app.state.templates
    
    rules = db.execute(
        select(BusinessRule).order_by(BusinessRule.rule_key)
    ).scalars().all()
    
    return templates.TemplateResponse(
        "admin/business_rules/list.html",
        {
            "request": request,
            "user": user,
            "rules": rules,
        },
    )


@router.get("/business-rules/{rule_id}/edit", response_class=HTMLResponse)
def edit_business_rule_form(
    request: Request,
    rule_id: int,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Display form for editing a business rule."""
    templates = request.app.state.templates
    
    rule = db.execute(
        select(BusinessRule).where(BusinessRule.rule_id == rule_id)
    ).scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return templates.TemplateResponse(
        "admin/business_rules/form.html",
        {
            "request": request,
            "user": user,
            "rule": rule,
        },
    )


@router.post("/business-rules/{rule_id}", response_class=HTMLResponse)
def update_business_rule(
    request: Request,
    rule_id: int,
    rule_value: str = Form(...),
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a business rule."""
    templates = request.app.state.templates
    
    rule = db.execute(
        select(BusinessRule).where(BusinessRule.rule_id == rule_id)
    ).scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    errors = []
    
    # Validate based on type
    if rule.value_type == "integer":
        try:
            int(rule_value)
        except ValueError:
            errors.append("Value must be a whole number")
    elif rule.value_type == "boolean":
        if rule_value.lower() not in ("true", "false", "1", "0", "yes", "no"):
            errors.append("Value must be true or false")
    elif rule.value_type == "choice" and rule.valid_options:
        valid = [v.strip() for v in rule.valid_options.split(",")]
        if rule_value not in valid:
            errors.append(f"Value must be one of: {', '.join(valid)}")
    
    if errors:
        return templates.TemplateResponse(
            "admin/business_rules/form.html",
            {
                "request": request,
                "user": user,
                "rule": rule,
                "errors": errors,
            },
            status_code=400,
        )
    
    audit = AuditService(db, user.employee_id, request.client.host if request.client else None)
    old_state = audit.capture_state(rule)
    
    rule.rule_value = rule_value.strip()
    rule.modified_at = datetime.utcnow()
    rule.modified_by = user.employee_id
    
    audit.log_update(rule, old_state)
    db.commit()
    
    return RedirectResponse(url="/admin/business-rules", status_code=302)


# =============================================================================
# Audit Log
# =============================================================================

@router.get("/audit-log", response_class=HTMLResponse)
def view_audit_log(
    request: Request,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
    table_name: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    performed_by: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=90),
):
    """View the audit log."""
    templates = request.app.state.templates
    
    # Build query
    query = select(AuditLog).order_by(AuditLog.performed_at.desc())
    
    # Date filter
    since = datetime.utcnow() - timedelta(days=days)
    query = query.where(AuditLog.performed_at >= since)
    
    if table_name:
        query = query.where(AuditLog.table_name == table_name)
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if performed_by:
        query = query.where(AuditLog.performed_by == performed_by)
    
    query = query.limit(500)
    
    entries = db.execute(query).scalars().all()
    
    # Get filter options
    tables = db.execute(
        select(AuditLog.table_name).distinct()
    ).scalars().all()
    
    actions = db.execute(
        select(AuditLog.action).distinct()
    ).scalars().all()
    
    employees = db.execute(
        select(Employee).where(Employee.is_active == True).order_by(Employee.last_name, Employee.first_name)
    ).scalars().all()
    
    return templates.TemplateResponse(
        "admin/audit_log/list.html",
        {
            "request": request,
            "user": user,
            "entries": entries,
            "tables": sorted(tables),
            "actions": sorted(actions),
            "employees": employees,
            "filters": {
                "table_name": table_name,
                "action": action,
                "performed_by": performed_by,
                "days": days,
            },
        },
    )


@router.get("/audit-log/{audit_id}", response_class=HTMLResponse)
def view_audit_entry(
    request: Request,
    audit_id: int,
    user: Employee = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """View a single audit log entry with full details."""
    templates = request.app.state.templates
    
    entry = db.execute(
        select(AuditLog).where(AuditLog.audit_id == audit_id)
    ).scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    
    return templates.TemplateResponse(
        "admin/audit_log/detail.html",
        {
            "request": request,
            "user": user,
            "entry": entry,
        },
    )