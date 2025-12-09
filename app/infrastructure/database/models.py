"""
SQLAlchemy database models.
Part of Infrastructure layer - persistence models.
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, JSON, Integer, Sequence, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSVECTOR, JSONB
from sqlalchemy.orm import relationship
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
    photo_url = Column(Text, nullable=True)  # Profile photo URL (base64 data URL)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    oauth_tokens = relationship("OAuthTokenModel", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettingsModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshTokenModel", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email={self.email}, provider={self.provider})>"


class OAuthTokenModel(Base):
    """
    OAuth token storage for calendar providers.
    Maps to the 'oauth_tokens' table in PostgreSQL.
    """

    __tablename__ = "oauth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # google, microsoft
    access_token = Column(Text, nullable=False)  # Encrypted in production
    refresh_token = Column(Text, nullable=True)  # Encrypted in production
    token_type = Column(String(50), default="Bearer", nullable=False)
    expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)  # Space-separated scopes
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="oauth_tokens")

    def __repr__(self) -> str:
        return f"<OAuthTokenModel(user_id={self.user_id}, provider={self.provider})>"


class UserSettingsModel(Base):
    """
    User settings for calendar and other preferences.
    Maps to the 'user_settings' table in PostgreSQL.
    """

    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    primary_calendar_provider = Column(String(50), nullable=True)  # google or microsoft
    language = Column(String(10), default="nl", nullable=False)  # nl, en
    timezone = Column(String(50), default="Europe/Amsterdam", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettingsModel(user_id={self.user_id}, primary_provider={self.primary_calendar_provider})>"


class ConversationModel(Base):
    """
    Conversation database model.
    Maps to the 'conversations' table in PostgreSQL.
    """

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    mode = Column(String(50), default="chat", nullable=False)  # chat, voice, note, scan
    meta = Column(JSON, nullable=True)  # Store extra info as JSON (renamed from metadata - reserved keyword)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel")
    messages = relationship("MessageModel", back_populates="conversation", cascade="all, delete-orphan", order_by="MessageModel.created_at")

    def __repr__(self) -> str:
        return f"<ConversationModel(id={self.id}, user_id={self.user_id}, mode={self.mode})>"


class MessageModel(Base):
    """
    Message database model.
    Maps to the 'messages' table in PostgreSQL.
    """

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True)  # For commands, attachments, etc. (renamed from metadata - reserved keyword)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("ConversationModel", back_populates="messages")

    def __repr__(self) -> str:
        return f"<MessageModel(id={self.id}, conversation_id={self.conversation_id}, role={self.role})>"


class PersonModel(Base):
    """
    Person database model.
    Maps to the 'persons' table in PostgreSQL.
    """

    __tablename__ = "persons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel")
    tasks = relationship("TaskModel", back_populates="delegated_person", foreign_keys="TaskModel.delegated_to")

    def __repr__(self) -> str:
        return f"<PersonModel(id={self.id}, name={self.name}, user_id={self.user_id})>"


class TaskModel(Base):
    """
    Task database model.
    Maps to the 'tasks' table in PostgreSQL.
    """

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_number = Column(Integer, Sequence('task_number_seq'), nullable=False, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    memo = Column(Text, nullable=True)
    delegated_to = Column(UUID(as_uuid=True), ForeignKey("persons.id"), nullable=True)
    due_date = Column(Text, nullable=True)  # Flexible text field
    priority = Column(String(20), default="medium", nullable=False)
    status = Column(String(50), default="new", nullable=False, index=True)
    status_description = Column(Text, nullable=True)
    tags = Column(ARRAY(Text), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel")
    delegated_person = relationship("PersonModel", back_populates="tasks", foreign_keys=[delegated_to])

    def __repr__(self) -> str:
        return f"<TaskModel(id={self.id}, task_number={self.task_number}, title={self.title})>"


class NoteGroupModel(Base):
    """
    NoteGroup database model.
    Maps to the 'note_groups' table in PostgreSQL.
    """

    __tablename__ = "note_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    color = Column(String(20), default="blue", nullable=False)
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel")
    notes = relationship("NoteModel", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NoteGroupModel(id={self.id}, name={self.name}, user_id={self.user_id})>"


class NoteModel(Base):
    """
    Note database model.
    Maps to the 'notes' table in PostgreSQL.
    """

    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("note_groups.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    color = Column(String(20), default="yellow", nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_checklist = Column(Boolean, default=False, nullable=False)
    categories = Column(ARRAY(String), nullable=True, default=[])
    search_vector = Column(TSVECTOR, nullable=True)  # For full-text search
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    user = relationship("UserModel")
    group = relationship("NoteGroupModel", back_populates="notes")
    items = relationship("NoteItemModel", back_populates="note", cascade="all, delete-orphan", order_by="NoteItemModel.sort_order")

    # Indexes
    __table_args__ = (
        Index('idx_notes_user_deleted', 'user_id', 'deleted_at'),
        Index('idx_notes_search', 'search_vector', postgresql_using='gin'),
    )

    def __repr__(self) -> str:
        return f"<NoteModel(id={self.id}, title={self.title}, user_id={self.user_id})>"


class NoteItemModel(Base):
    """
    NoteItem database model (for checklist items).
    Maps to the 'note_items' table in PostgreSQL.
    """

    __tablename__ = "note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id = Column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_checked = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    note = relationship("NoteModel", back_populates="items")

    def __repr__(self) -> str:
        return f"<NoteItemModel(id={self.id}, note_id={self.note_id}, content={self.content[:30]})>"


class InboxItemModel(Base):
    """
    InboxItem database model.
    Maps to the 'inbox_items' table in PostgreSQL.
    """

    __tablename__ = "inbox_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # email, calendar_event, message, etc.
    source = Column(String(100), nullable=False)  # gmail, outlook, manual, etc.
    status = Column(String(50), nullable=False, default="unprocessed")
    priority = Column(String(20), nullable=False, default="medium")
    subject = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=True)
    ai_suggestion = Column(JSONB, nullable=True)
    user_decision = Column(JSONB, nullable=True)
    linked_items = Column(JSONB, nullable=True, default=[])
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel")

    # Indexes defined in migration

    def __repr__(self) -> str:
        return f"<InboxItemModel(id={self.id}, type={self.type}, status={self.status})>"


class RefreshTokenModel(Base):
    """
    Refresh token database model for JWT token refresh.
    Maps to the 'refresh_tokens' table in PostgreSQL.
    """

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshTokenModel(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
