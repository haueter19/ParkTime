# ParkTime

Time tracking system for the Parking Division.

## Features

- Employee time entry with weekly view
- Work codes for categorizing time (regular, overtime, leave types)
- Role-based access (employee, manager, admin)
- Full audit trail of all changes
- HTMX-powered responsive interface

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy
- **Database**: SQL Server
- **Frontend**: Jinja2 templates + HTMX + Bootstrap 5
- **Migrations**: Alembic

## Setup

### 1. Prerequisites

- Python 3.10+
- SQL Server (or SQL Server Express)
- ODBC Driver 17 for SQL Server

### 2. Create Database

```sql
CREATE DATABASE parktime;
GO

-- Create a login for the application
CREATE LOGIN parktime_app WITH PASSWORD = 'your_secure_password';
GO

USE parktime;
CREATE USER parktime_app FOR LOGIN parktime_app;
ALTER ROLE db_owner ADD MEMBER parktime_app;
GO
```

### 3. Install Dependencies

```bash
cd parktime
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 5. Run Migrations

```bash
# Test database connection
python -m scripts.db_manage check

# Run all migrations (creates tables and seeds data)
python -m scripts.db_manage migrate

# Set admin password
python -m scripts.db_manage setpassword
# Enter: admin
# Enter your password
```

### 6. Start the Server

```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000 and log in with the admin account.

## Database Management Commands

```bash
python -m scripts.db_manage check       # Test connection
python -m scripts.db_manage migrate     # Run pending migrations
python -m scripts.db_manage rollback    # Rollback last migration (dev only)
python -m scripts.db_manage current     # Show current version
python -m scripts.db_manage history     # Show migration history
python -m scripts.db_manage reset       # Drop and recreate (dev only)
python -m scripts.db_manage setpassword # Set user password
```

## Project Structure

```
parktime/
├── alembic/                # Database migrations
│   ├── versions/           # Migration files
│   └── env.py             # Alembic configuration
├── app/
│   ├── models/            # SQLAlchemy ORM models
│   ├── routes/            # FastAPI route handlers
│   ├── services/          # Business logic
│   ├── templates/         # Jinja2 HTML templates
│   ├── config.py          # Application settings
│   ├── database.py        # Database connection
│   ├── dependencies.py    # FastAPI dependencies
│   └── main.py            # Application factory
├── scripts/
│   └── db_manage.py       # Database CLI
├── alembic.ini            # Alembic settings
├── requirements.txt       # Python dependencies
└── .env.example           # Environment template
```

## Default Accounts

After running migrations, an `admin` account is created with no password.
Use `python -m scripts.db_manage setpassword` to set the initial password.

## Default Work Codes

| Code | Description | Type |
|------|-------------|------|
| REG | Regular Hours | work |
| OT | Overtime | work |
| TRAINING | Training | work |
| VAC | Vacation | leave_paid |
| SICK | Sick Leave | leave_paid |
| PERSONAL | Personal Day | leave_paid |
| HOLIDAY | Holiday | leave_paid |
| JURY | Jury Duty | leave_paid |
| BEREAVEMENT | Bereavement | leave_paid |
| LWOP | Leave Without Pay | leave_unpaid |

## Creating New Migrations

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description of changes"

# Create empty migration
alembic revision -m "description"

# Run migrations
alembic upgrade head
```

## License

Internal use only - Parking Division
