"""
監査ログ API
設計仕様書 3.1 監査ログ API に準拠
ISO27001 A.5.28 – 監査ログの保護
"""

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.audit_log import AuditLog

router = APIRouter()


@router.get("/audit-logs", summary="監査ログ検索")
async def search_audit_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None),
    source_system: str | None = Query(default=None),
    result: str | None = Query(default=None),
    actor_user_id: uuid.UUID | None = Query(default=None),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """監査ログをフィルタ・ページネーションで検索"""
    query = select(AuditLog).order_by(AuditLog.event_time.desc())

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if source_system:
        query = query.where(AuditLog.source_system == source_system)
    if result:
        query = query.where(AuditLog.result == result)
    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if from_time:
        query = query.where(AuditLog.event_time >= from_time)
    if to_time:
        query = query.where(AuditLog.event_time <= to_time)

    query = query.offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(query)).scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "event_id": str(log.event_id),
                "event_time": log.event_time.isoformat(),
                "event_type": log.event_type,
                "source_system": log.source_system,
                "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
                "action": log.action,
                "result": log.result,
                "risk_score": log.risk_score,
            }
            for log in rows
        ],
        "meta": {"page": page, "per_page": per_page},
        "errors": [],
    }


@router.get("/audit-logs/export", summary="ログ CSV エクスポート")
async def export_audit_logs(
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """監査ログを CSV でエクスポート（ISO27001 A.5.28 証跡出力）"""
    query = select(AuditLog).order_by(AuditLog.event_time.asc())
    if from_time:
        query = query.where(AuditLog.event_time >= from_time)
    if to_time:
        query = query.where(AuditLog.event_time <= to_time)

    rows = (await db.execute(query)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["event_id", "event_time", "event_type", "source_system", "actor_ip",
         "action", "result", "risk_score", "hash"]
    )
    for log in rows:
        writer.writerow([
            log.event_id, log.event_time, log.event_type, log.source_system,
            log.actor_ip, log.action, log.result, log.risk_score, log.hash,
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
