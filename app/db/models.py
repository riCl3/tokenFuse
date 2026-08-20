from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    monthly_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=settings.default_monthly_budget_usd
    )
    warn_pct: Mapped[float] = mapped_column(default=settings.budget_warn_pct)
    fallback_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    usage_events: Mapped[list[UsageEvent]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="api_keys")
    usage_events: Mapped[list[UsageEvent]] = relationship(back_populates="api_key")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    prompt_tokens: Mapped[int] = mapped_column()
    completion_tokens: Mapped[int] = mapped_column()
    total_tokens: Mapped[int] = mapped_column()
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    streamed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="usage_events")
    api_key: Mapped[ApiKey | None] = relationship(back_populates="usage_events")

    __table_args__ = (
        Index("ix_usage_events_project_created", "project_id", "created_at"),
    )