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
    python -m scripts.db_manage verify       # Verify schema and core tables (interactive)
"""

import sys
from getpass import getpass

from app.config import get_settings
from app.database import check_connection, get_db_context, engine


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
        
        auth = AuthService(db)
        auth.set_password(employee, password)
        db.commit()
        
        print(f"Password updated for {employee.display_name}")
    
    return True


def cmd_verify():
    """Verify the configured schema and presence of critical tables.

    This help command checks whether the configured schema (e.g. 'pt') exists
    and whether the `employees` table exists in that schema. If the schema
    is missing it can optionally be created (requires permission) and then
    migrations can be run to create the tables.
    """
    import sqlalchemy as sa

    schema = settings.db_schema
    print(f"Verifying database schema: {schema or 'default (dbo)'}")

    with engine.connect() as conn:
        # Check schema existence
        if schema:
            schema_row = conn.execute(
                sa.text("SELECT name FROM sys.schemas WHERE name = :s"), {"s": schema}
            ).scalar_one_or_none()

            if not schema_row:
                print(f"Schema '{schema}' does not exist in database {settings.db_name}.")
                create = input("Create schema now using current DB user? (requires CREATE SCHEMA permission) (yes/no): ")
                if create.strip().lower() == "yes":
                    try:
                        # Validate schema name (basic safety)
                        if not schema.replace("_", "").isalnum():
                            print("Schema name contains strange characters — aborting create for safety.")
                        else:
                            conn.execute(sa.text(f"CREATE SCHEMA {schema}"))
                            print(f"Schema '{schema}' created.")
                    except Exception as e:
                        print(f"Failed to create schema: {e}")
                        print("You can create the schema with a privileged account or run migrations against the default schema.")
            else:
                print(f"Schema '{schema}' exists.")

        # Check for employees table in the target schema
        tbl_schema = schema or conn.execute(sa.text("SELECT SCHEMA_NAME()")).scalar_one()
        table_row = conn.execute(
            sa.text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :s AND TABLE_NAME = 'employees'"
            ), {"s": tbl_schema}
        ).scalar_one_or_none()

        if table_row:
            print(f"Found 'employees' table in schema '{tbl_schema}'.")
        else:
            print(f"Table 'employees' was NOT found in schema '{tbl_schema}'.")
            migrate = input("Run migrations now to create missing tables? (yes/no): ")
            if migrate.strip().lower() == "yes":
                from alembic.config import Config
                from alembic import command

                try:
                    alembic_cfg = Config("alembic.ini")
                    print("Running migrations...")
                    command.upgrade(alembic_cfg, "head")
                    print("Migrations complete — re-check tables.")
                except Exception as e:
                    print(f"Migrations failed: {e}")
                    return False

                # Re-check table
                table_row = conn.execute(
                    sa.text(
                        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :s AND TABLE_NAME = 'employees'"
                    ), {"s": tbl_schema}
                ).scalar_one_or_none()

                if table_row:
                    print("Employees table now exists — verification complete.")
                else:
                    print("Employees table still missing after migrations — check logs and permissions.")
                    return False

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
    "verify": cmd_verify,
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
