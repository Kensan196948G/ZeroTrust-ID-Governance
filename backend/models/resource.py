"""リソースモデル（アクセス管理対象リソース）"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(50),
        CheckConstraint(
            "resource_type IN ('application','fileserver','database','api','sharepoint')"
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    owner_department: Mapped[str | None] = mapped_column(String(200))
    classification: Mapped[str] = mapped_column(String(20), default="internal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
