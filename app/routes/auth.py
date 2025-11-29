# ParkTime - Authentication Routes
# Login, logout, and password management

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_current_user_optional,
    SESSION_COOKIE_NAME,
)
from app.models.employee import Employee
from app.services.auth import AuthService, AuthenticationError


router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    user: Employee | None = Depends(get_current_user_optional),
    error: str | None = None,
):
    """
    Display the login form.
    
    If already logged in, redirect to home.
    """
    if user:
        return RedirectResponse(url="/", status_code=302)
    
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": error,
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Process login form submission.
    
    On success: Set session cookie and redirect to home.
    On failure: Re-render login page with error.
    """
    auth = AuthService(db)
    templates = request.app.state.templates
    
    try:
        employee, session = auth.login(username, password)
        
        # Update session with request metadata
        session.ip_address = request.client.host if request.client else None
        session.user_agent = request.headers.get("user-agent", "")[:500]
        db.commit()
        
        # Create redirect response with session cookie
        redirect = RedirectResponse(url="/", status_code=302)
        redirect.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session.session_token,
            httponly=True,  # Not accessible via JavaScript
            secure=False,   # Set to True in production with HTTPS
            samesite="lax",
            max_age=60 * 60 * 8,  # 8 hours
        )
        
        return redirect
        
    except AuthenticationError as e:
        # Re-render login page with error
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": str(e),
                "username": username,  # Preserve username input
            },
            status_code=401,
        )


@router.get("/logout")
@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Log out the current user.
    
    Invalidates the session and clears the cookie.
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    
    if session_token:
        auth = AuthService(db)
        auth.logout(session_token)
    
    # Redirect to login with cookie cleared
    redirect = RedirectResponse(url="/login", status_code=302)
    redirect.delete_cookie(SESSION_COOKIE_NAME)
    
    return redirect


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(
    request: Request,
    user: Employee = Depends(get_current_user),
    success: bool = False,
    error: str | None = None,
):
    """Display the change password form."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "auth/change_password.html",
        {
            "request": request,
            "user": user,
            "success": success,
            "error": error,
        },
    )


@router.post("/change-password")
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process password change form."""
    templates = request.app.state.templates
    
    # Validate new password
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "user": user,
                "error": "New passwords do not match",
            },
            status_code=400,
        )
    
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "user": user,
                "error": "Password must be at least 8 characters",
            },
            status_code=400,
        )
    
    # Attempt password change
    auth = AuthService(db)
    
    try:
        auth.change_password(user, current_password, new_password)
        
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "user": user,
                "success": True,
            },
        )
        
    except AuthenticationError as e:
        return templates.TemplateResponse(
            "auth/change_password.html",
            {
                "request": request,
                "user": user,
                "error": str(e),
            },
            status_code=400,
        )
