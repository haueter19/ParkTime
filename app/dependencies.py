# ParkTime - Authentication Dependencies
# FastAPI dependencies for protecting routes

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import Employee
from app.services.auth import AuthService


# Cookie name for session token
SESSION_COOKIE_NAME = "parktime_session"


def get_session_token(request: Request) -> Optional[str]:
    """
    Extract session token from request cookies.
    
    Returns None if no session cookie is present.
    """
    return request.cookies.get(SESSION_COOKIE_NAME)


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[Employee]:
    """
    Get the current user if logged in, None otherwise.
    
    Use this for pages that work differently for logged-in vs anonymous users.
    
    Usage:
        @router.get("/")
        def home(user: Optional[Employee] = Depends(get_current_user_optional)):
            if user:
                return f"Welcome back, {user.display_name}!"
            return "Please log in"
    """
    session_token = get_session_token(request)
    if not session_token:
        return None
    
    auth = AuthService(db)
    return auth.validate_session(session_token)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Employee:
    """
    Get the current logged-in user or raise 401.
    
    Use this to protect routes that require authentication.
    
    Usage:
        @router.get("/entries")
        def list_entries(user: Employee = Depends(get_current_user)):
            # user is guaranteed to be authenticated
            return get_entries_for_user(user.employee_id)
    """
    user = get_current_user_optional(request, db)
    
    if not user:
        # For HTMX requests, we might want to return a different response
        # For now, redirect to login
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"HX-Redirect": "/login"} if request.headers.get("HX-Request") else {},
        )
    
    return user


def require_admin(
    user: Employee = Depends(get_current_user),
) -> Employee:
    """
    Require the current user to be an admin.
    
    Usage:
        @router.get("/admin/users")
        def list_users(user: Employee = Depends(require_admin)):
            # user is guaranteed to be an admin
            ...
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_manager(
    user: Employee = Depends(get_current_user),
) -> Employee:
    """
    Require the current user to be a manager or admin.
    
    Usage:
        @router.get("/team/entries")
        def list_team_entries(user: Employee = Depends(require_manager)):
            # user is guaranteed to be manager or admin
            ...
    """
    if not user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return user


class RequireRole:
    """
    Flexible role checker dependency.
    
    Usage:
        @router.get("/special")
        def special_page(user: Employee = Depends(RequireRole("admin", "manager"))):
            ...
    """
    
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = set(allowed_roles)
    
    def __call__(self, user: Employee = Depends(get_current_user)) -> Employee:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {' or '.join(self.allowed_roles)}",
            )
        return user


def can_edit_employee_time(
    target_employee_id: int,
    user: Employee = Depends(get_current_user),
) -> bool:
    """
    Check if current user can edit time entries for target employee.
    
    Rules:
        - Admins can edit anyone
        - Managers can edit their direct reports
        - Employees can only edit their own
    
    Usage in route:
        @router.put("/entries/{entry_id}")
        def update_entry(
            entry_id: int,
            user: Employee = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            entry = get_entry(entry_id)
            if not can_edit_employee_time(entry.employee_id, user):
                raise HTTPException(403, "Cannot edit this entry")
            ...
    """
    return user.can_view_employee(target_employee_id)
