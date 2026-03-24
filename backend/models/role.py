"""
ロールモデル
設計仕様書 2.1 roles テーブルに準拠
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import Boolean, CheckConstraint, DateTime, Interval, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("role_type IN ('business','technical','privileged')"),
        nullable=False,
    )
    is_privileged: Mapped[bool] = mapped_column(Boolean, default=False)

    # PIM: 特権ロール最大保持時間（例: 8時間）
    max_duration: Mapped[timedelta | None] = mapped_column(Interval)

    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # リレーション
    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.role_name} ({self.role_type})>"


class UserRole(Base):
    """ユーザ-ロール多対多中間テーブル"""

    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ForeignKey は循環インポート回避のため文字列で指定
        __import__("sqlalchemy").ForeignKey("users.id"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        __import__("sqlalchemy").ForeignKey("roles.id"),
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")
