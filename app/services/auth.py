# ParkTime - Authentication Service
# Password hashing, session management, login/logout

from datetime import datetime, timedelta
from typing import Optional
import secrets

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.employee import Employee


settings = get_settings()

# Password hashing configuration
# Using bcrypt with automatic salt generation
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Balance security vs. speed
)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks permission."""
    pass


class AuthService:
    """
    Authentication service for login, logout, and session management.
    
    Usage:
        auth = AuthService(db)
        
        # Login
        employee, session_token = auth.login("jsmith", "password123")
        
        # Validate session
        employee = auth.validate_session(session_token)
        
        # Logout
        auth.logout(session_token)
    
    Sessions are stored in the database for easy invalidation
    and audit trail.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def hash_password(self, plain_password: str) -> str:
        """
        Hash a plain text password.
        
        Uses bcrypt with automatic salt generation.
        """
        return pwd_context.hash(plain_password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain text password against a hash.
        
        Returns True if password matches, False otherwise.
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # Invalid hash format or other error
            return False
    
    def authenticate(self, username: str, password: str) -> Employee:
        """
        Authenticate a user by username and password.
        
        Args:
            username: The user's username
            password: The plain text password
            
        Returns:
            The authenticated Employee object
            
        Raises:
            AuthenticationError: If credentials are invalid or account is inactive
        """
        # Find the user
        employee = self.db.execute(
            select(Employee).where(Employee.username == username)
        ).scalar_one_or_none()
        
        if not employee:
            # Don't reveal whether username exists
            raise AuthenticationError("Invalid username or password")
        
        if not employee.is_active:
            raise AuthenticationError("Account is inactive")
        
        if not employee.password_hash:
            raise AuthenticationError("Account has no password set")
        
        if not self.verify_password(password, employee.password_hash):
            raise AuthenticationError("Invalid username or password")
        
        return employee
    
    def generate_session_token(self) -> str:
        """
        Generate a cryptographically secure session token.
        
        Returns a 64-character hex string (256 bits of entropy).
        """
        return secrets.token_hex(32)
    
    def login(self, username: str, password: str) -> tuple[Employee, "UserSession"]:
        """
        Authenticate user and create a new session.
        
        Args:
            username: The user's username
            password: The plain text password
            
        Returns:
            Tuple of (Employee, UserSession)
            
        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Import here to avoid circular dependency
        from app.models.user_session import UserSession
        
        employee = self.authenticate(username, password)
        
        # Create session
        session_token = self.generate_session_token()
        expires_at = datetime.utcnow() + timedelta(minutes=settings.session_expire_minutes)
        
        session = UserSession(
            employee_id=employee.employee_id,
            session_token=session_token,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
        )
        
        self.db.add(session)
        self.db.commit()
        
        return employee, session
    
    def validate_session(self, session_token: str) -> Optional[Employee]:
        """
        Validate a session token and return the associated employee.
        
        Args:
            session_token: The session token from cookie
            
        Returns:
            The Employee if session is valid, None otherwise
        """
        from app.models.user_session import UserSession
        
        session = self.db.execute(
            select(UserSession)
            .where(UserSession.session_token == session_token)
            .where(UserSession.is_active == True)
        ).scalar_one_or_none()
        
        if not session:
            return None
        
        # Check expiration
        if session.expires_at < datetime.utcnow():
            session.is_active = False
            self.db.commit()
            return None
        
        # Get the employee
        employee = self.db.execute(
            select(Employee)
            .where(Employee.employee_id == session.employee_id)
            .where(Employee.is_active == True)
        ).scalar_one_or_none()
        
        if not employee:
            return None
        
        # Update last activity
        session.last_activity_at = datetime.utcnow()
        self.db.commit()
        
        return employee
    
    def logout(self, session_token: str) -> bool:
        """
        Invalidate a session.
        
        Args:
            session_token: The session token to invalidate
            
        Returns:
            True if session was found and invalidated, False otherwise
        """
        from app.models.user_session import UserSession
        
        session = self.db.execute(
            select(UserSession)
            .where(UserSession.session_token == session_token)
        ).scalar_one_or_none()
        
        if not session:
            return False
        
        session.is_active = False
        session.logged_out_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def logout_all_sessions(self, employee_id: int) -> int:
        """
        Invalidate all sessions for an employee.
        
        Useful for password changes or security incidents.
        
        Args:
            employee_id: The employee whose sessions to invalidate
            
        Returns:
            Number of sessions invalidated
        """
        from app.models.user_session import UserSession
        
        result = self.db.execute(
            select(UserSession)
            .where(UserSession.employee_id == employee_id)
            .where(UserSession.is_active == True)
        ).scalars().all()
        
        count = 0
        for session in result:
            session.is_active = False
            session.logged_out_at = datetime.utcnow()
            count += 1
        
        self.db.commit()
        return count
    
    def set_password(self, employee: Employee, new_password: str) -> None:
        """
        Set or update an employee's password.
        
        Args:
            employee: The employee object
            new_password: The new plain text password
        """
        employee.password_hash = self.hash_password(new_password)
        self.db.commit()
    
    def change_password(
        self,
        employee: Employee,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change an employee's password (requires current password).
        
        Args:
            employee: The employee object
            current_password: The current plain text password
            new_password: The new plain text password
            
        Raises:
            AuthenticationError: If current password is wrong
        """
        if not self.verify_password(current_password, employee.password_hash):
            raise AuthenticationError("Current password is incorrect")
        
        self.set_password(employee, new_password)
        
        # Optionally invalidate other sessions
        # self.logout_all_sessions(employee.employee_id)
