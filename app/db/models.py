import uuid     #Python's built-in module for generating UUIDs (Universally Unique Identifiers)
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Enum as SQLAEnum ,DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.domain.status import ApplicationStatus

from sqlalchemy import JSON

#mapped - SQLAlchemy's modern type-annotation system for ORM attributes.
#Think of Mapped as telling SQLAlchemy:This Python variable is connected to a database column.
#mapped_column - column definition with its database rules.
#relationship - creates the Python/ORM-level connection.
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)     #uuid.uuid4 is a function that generates a new UUID.
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    applications: Mapped[list["Application"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    role_title: Mapped[str] = mapped_column(String, nullable=False)
    current_status: Mapped[ApplicationStatus] = mapped_column(
        SQLAEnum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.APPLIED,
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="applications")
    status_history: Mapped[list["StatusHistory"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    from_status: Mapped[ApplicationStatus | None] = mapped_column(SQLAEnum(ApplicationStatus, name="application_status"), nullable=True)
    to_status: Mapped[ApplicationStatus] = mapped_column(SQLAEnum(ApplicationStatus, name="application_status"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    application: Mapped["Application"] = relationship(back_populates="status_history")


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)