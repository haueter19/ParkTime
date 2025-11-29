# ParkTime - Base Model and Mixins

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, ForeignKey, MetaData
from app.config import get_settings
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr


settings = get_settings()
SCHEMA = settings.db_schema

# Use a metadata instance with a default schema so models and Alembic agree
_metadata = MetaData(schema=SCHEMA) if SCHEMA else MetaData()


class Base(DeclarativeBase):
    """Base class for all models."""
    metadata = _metadata


class TimestampMixin:
    """Mixin that adds created_at timestamp to models."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )


class AuditMixin(TimestampMixin):
    """
    Mixin that adds full audit fields to models.
    Includes created_at, created_by, modified_at, modified_by.
    
    Use this for tables where we need to track who made changes.
    """
    
    @declared_attr
    def created_by(cls) -> Mapped[int]:
        return mapped_column(
            Integer,
            ForeignKey("employees.employee_id"),
            nullable=False
        )
    
    modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=datetime.utcnow
    )
    
    @declared_attr
    def modified_by(cls) -> Mapped[Optional[int]]:
        return mapped_column(
            Integer,
            ForeignKey("employees.employee_id"),
            nullable=True
        )
