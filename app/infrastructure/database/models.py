"""
SQLAlchemy database models.
Part of Infrastructure layer - persistence models.
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.infrastructure.database.session import Base


class UserModel(Base):
    """
    User database model (SQLAlchemy ORM).
    Maps to the 'users' table in PostgreSQL.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)  # google, microsoft, local
    hashed_password = Column(String(255), nullable=True)  # Only for local users
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email={self.email}, provider={self.provider})>"
