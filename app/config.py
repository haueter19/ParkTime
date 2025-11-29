# ParkTime - Configuration
# Application settings loaded from environment variables

from functools import lru_cache
from typing import Optional
#from db_manager import ConnectionManager
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Create a .env file in the project root for local development:
    
        # .env
        PARKTIME_DB_SERVER=localhost
        PARKTIME_DB_NAME=parktime
        PARKTIME_DB_USER=parktime_app
        PARKTIME_DB_PASSWORD=your_password_here
        PARKTIME_SECRET_KEY=your-secret-key-change-in-production
    
    For production, set these as actual environment variables.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="PARKTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "ParkTime"
    debug: bool = False
    secret_key: str = "Parking_Division_Timekeeping"
    
    # Database - SQL Server connection
    db_server: str = "localhost"
    db_port: int = 1433
    db_name: str = "parktime"
    db_user: str = "parktime_app"
    db_password: str = "parktime_password"

    # Optional: Schema for all tables (e.g., "parking", "hr")
    # If not set, defaults to dbo
    db_schema: Optional[str] = 'pt'
    
    # Optional: Use Windows Authentication instead of SQL auth
    # Set to True and leave db_user/db_password empty
    db_trusted_connection: bool = True
    
    # Connection pool settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # Recycle connections after 30 min
    
    # Session settings
    session_expire_minutes: int = 480  # 8 hours
    
    @property
    def database_url(self) -> str:
        """
        Build the SQL Server connection URL for SQLAlchemy.
        
        Uses pyodbc with ODBC Driver 17 or 18 for SQL Server.
        """
        if self.db_trusted_connection:
            # Windows Authentication
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.db_server},{self.db_port};"
                f"DATABASE={self.db_name};"
                f"Trusted_Connection=yes;"
            )
        else:
            # SQL Server Authentication
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.db_server},{self.db_port};"
                f"DATABASE={self.db_name};"
                f"UID={self.db_user};"
                f"PWD={self.db_password};"
            )
        
        # SQLAlchemy URL format for pyodbc
        from urllib.parse import quote_plus
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
    
    @property
    def database_url_async(self) -> str:
        """
        Build async connection URL using aioodbc.
        
        Only needed if you want async database operations.
        For internal apps, sync is usually fine.
        """
        # For now, we'll stick with sync operations
        raise NotImplementedError("Async not implemented - use sync database_url")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Using lru_cache ensures we only load settings once.
    """
    return Settings()
