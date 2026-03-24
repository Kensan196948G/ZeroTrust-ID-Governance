"""
監査ログモデル
設計仕様書 2.1 audit_logs テーブルに準拠
チェーンハッシュによる改ざん防止（ISO27001 A.5.28）
"""

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_ip: Mapped[str | None] = mapped_column(INET)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    target_resource: Mapped[str | None] = mapped_column(String(500))

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)

    # SHA256 チェーンハッシュ（改ざん検知）
    hash: Mapped[str | None] = mapped_column(String(64))

    @staticmethod
    def compute_hash(log_entry: dict, previous_hash: str = "") -> str:
        """チェーンハッシュ生成（設計仕様書 5.3 準拠）"""
        content = json.dumps(log_entry, sort_keys=True, ensure_ascii=False)
        combined = f"{previous_hash}{content}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} {self.result} @ {self.event_time}>"
