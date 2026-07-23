from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    external_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64))
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    last_event_created: Mapped[int] = mapped_column(Integer, default=0)
    last_event_rank: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    user: Mapped[User] = relationship(back_populates="subscriptions")


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(255))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


def build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def initialise_database(engine: Engine) -> None:
    database_path = engine.url.database
    if engine.url.drivername.startswith("sqlite") and database_path not in {None, ":memory:"}:
        from pathlib import Path

        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def upsert_user(session: Session, subject: str, email: str | None) -> User:
    user = session.scalar(select(User).where(User.external_subject == subject))
    if user is None:
        user = User(external_subject=subject, email=email)
        session.add(user)
        session.flush()
    elif email and user.email != email:
        user.email = email
        session.flush()
    return user
