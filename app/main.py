# ParkTime - Main Application
# FastAPI application factory and startup

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import check_connection


settings = get_settings()

# Paths
APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    
    Runs on startup and shutdown.
    """
    # Startup
    print(f"Starting {settings.app_name}...")
    
    # Verify database connection
    try:
        check_connection()
        print("Database connection: OK")
    except Exception as e:
        print(f"Database connection: FAILED - {e}")
        # In production, you might want to raise here to prevent startup
        if not settings.debug:
            raise
    
    yield
    
    # Shutdown
    print(f"Shutting down {settings.app_name}...")


def create_app() -> FastAPI:
    """
    Application factory.
    
    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        description="Time tracking system for Parking Division",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    
    # Static files (CSS, JS)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    
    # Templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    
    # Make templates available to routes via app.state
    app.state.templates = templates
    
    # Include routers
    from app.routes import auth, entries, admin, team
    app.include_router(auth.router)
    app.include_router(entries.router)
    app.include_router(admin.router)
    app.include_router(team.router)
    
    # Future routers (uncomment as implemented)
    # from app.routes import employees, work_codes, reports
    # app.include_router(reports.router)
    
    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint for monitoring."""
        try:
            check_connection()
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {e}"
        
        return {
            "status": "ok",
            "app": settings.app_name,
            "database": db_status,
        }
    
    # Root route - redirect based on auth status
    from app.dependencies import get_current_user_optional
    from app.database import get_db
    from fastapi import Depends
    from fastapi.responses import RedirectResponse
    from sqlalchemy.orm import Session
    
    @app.get("/")
    def root(
        request: Request,
        user = Depends(get_current_user_optional),
    ):
        """Root route - show dashboard or redirect to login."""
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # For now, just show a welcome message
        # Later this will be the dashboard/entries page
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "user": user,
            }
        )
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
    )
