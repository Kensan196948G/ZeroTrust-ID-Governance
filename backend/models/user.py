"""
ユーザモデル
設計仕様書 2.1 users テーブルに準拠
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.database import Base

if TYPE_CHECKING:
    from models.department import Department
    from models.role import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    job_title: Mapped[str | None] = mapped_column(String(200))
    user_type: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("user_type IN ('employee','contractor','partner','admin')"),
        nullable=False,
    )
    account_status: Mapped[str] = mapped_column(String(20), default="active")

    # 外部システム連携 ID
    entra_object_id: Mapped[str | None] = mapped_column(String(36))
    ad_dn: Mapped[str | None] = mapped_column(Text)
    hengeone_id: Mapped[str | None] = mapped_column(String(100))

    # 在籍情報
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # セキュリティ
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("risk_score BETWEEN 0 AND 100"),
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # リレーション
    department: Mapped["Department"] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.user_type})>"
