#!/usr/bin/env python
"""
ParkTime - Database Management CLI

Usage:
    python -m scripts.db_manage check       # Test database connection
    python -m scripts.db_manage migrate     # Run pending migrations
    python -m scripts.db_manage rollback    # Rollback last migration
    python -m scripts.db_manage current     # Show current migration version
    python -m scripts.db_manage history     # Show migration history
    python -m scripts.db_manage reset       # Drop all and recreate (dev only)
    python -m scripts.db_manage setpassword # Set password for a user
"""

import sys
from getpass import getpass

from app.config import get_settings
from app.database import check_connection, get_db_context


settings = get_settings()


def cmd_check():
    """Test database connection."""
    print(f"Connecting to: {settings.db_server}/{settings.db_name}")
    try:
        check_connection()
        print("Connection successful!")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def cmd_migrate():
    """Run pending Alembic migrations."""
    from alembic.config import Config
    from alembic import command
    
    print("Running migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Migrations complete!")
    return True


def cmd_rollback():
    """Rollback the last migration."""
    if not settings.debug:
        print("ERROR: rollback is only available in debug mode")
        return False
    
    from alembic.config import Config
    from alembic import command
    
    print("Rolling back last migration...")
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, "-1")
    print("Rollback complete!")
    return True


def cmd_current():
    """Show current migration version."""
    from alembic.config import Config
    from alembic import command
    
    alembic_cfg = Config("alembic.ini")
    command.current(alembic_cfg)
    return True


def cmd_history():
    """Show migration history."""
    from alembic.config import Config
    from alembic import command
    
    alembic_cfg = Config("alembic.ini")
    command.history(alembic_cfg)
    return True


def cmd_reset():
    """Drop all tables and recreate with migrations."""
    if not settings.debug:
        print("ERROR: reset is only available in debug mode")
        return False
    
    confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Aborted")
        return False
    
    from alembic.config import Config
    from alembic import command
    
    alembic_cfg = Config("alembic.ini")
    
    print("Rolling back all migrations...")
    try:
        command.downgrade(alembic_cfg, "base")
    except Exception as e:
        print(f"Rollback failed (maybe no tables exist): {e}")
    
    print("Running all migrations...")
    command.upgrade(alembic_cfg, "head")
    
    print("Reset complete!")
    return True


def cmd_setpassword():
    """Set password for a user."""
    from app.services.auth import AuthService
    from app.models.employee import Employee
    from sqlalchemy import select
    
    username = input("Username: ").strip()
    if not username:
        print("Username required")
        return False
    
    with get_db_context() as db:
        employee = db.execute(
            select(Employee).where(Employee.username == username)
        ).scalar_one_or_none()
        
        if not employee:
            print(f"User '{username}' not found")
            return False
        
        password = getpass("New password: ")
        confirm = getpass("Confirm password: ")
        
        if password != confirm:
            print("Passwords do not match")
            return False
        
        if len(password) < 8:
            print("Password must be at least 8 characters")
            return False
        
        # Check byte length for bcrypt (72 byte limit)
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            print(f"Password is too long ({len(password_bytes)} bytes).")
            print("Bcrypt has a 72-byte limit. Use ASCII characters and keep password under 72 bytes.")
            print("Tip: Special Unicode characters can use multiple bytes each.")
            return False
        
        auth = AuthService(db)
        auth.set_password(employee, password)
        db.commit()
        
        print(f"Password updated for {employee.display_name}")
    
    return True


def cmd_help():
    """Show help."""
    print(__doc__)
    return True


COMMANDS = {
    "check": cmd_check,
    "migrate": cmd_migrate,
    "rollback": cmd_rollback,
    "current": cmd_current,
    "history": cmd_history,
    "reset": cmd_reset,
    "setpassword": cmd_setpassword,
    "help": cmd_help,
}


def main():
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        cmd_help()
        sys.exit(1)
    
    success = COMMANDS[command]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()