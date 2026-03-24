"""アクセス申請 API（GOV-003 セルフサービスポータル申請）"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.access_request import AccessRequest

router = APIRouter()


class AccessRequestCreate(BaseModel):
    target_user_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    resource_id: uuid.UUID | None = None
    request_type: str = "grant"
    justification: str
    expires_at: datetime | None = None


class AccessRequestResponse(BaseModel):
    id: uuid.UUID
    request_type: str
    justification: str
    status: str
    created_at: datetime
    expires_at: datetime | None = None
    model_config = {"from_attributes": True}


@router.get("/access-requests", summary="申請一覧")
async def list_requests(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(AccessRequest).order_by(AccessRequest.created_at.desc()).limit(100)
    )
    requests = result.scalars().all()
    return {
        "success": True,
        "data": [AccessRequestResponse.model_validate(r).model_dump() for r in requests],
        "errors": [],
    }


@router.post("/access-requests", status_code=201, summary="新規アクセス申請")
async def create_request(
    payload: AccessRequestCreate,
    requester_id: uuid.UUID,  # 本番は JWT から取得
    db: AsyncSession = Depends(get_db),
) -> dict:
    req = AccessRequest(requester_id=requester_id, **payload.model_dump())
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {"success": True, "data": AccessRequestResponse.model_validate(req).model_dump(), "errors": []}


@router.get("/access-requests/pending", summary="承認待ち一覧")
async def pending_requests(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(AccessRequest).where(AccessRequest.status == "pending")
    )
    requests = result.scalars().all()
    return {
        "success": True,
        "data": [AccessRequestResponse.model_validate(r).model_dump() for r in requests],
        "errors": [],
    }


@router.patch("/access-requests/{request_id}", summary="申請承認・却下")
async def update_request(
    request_id: uuid.UUID,
    action: str,  # "approve" or "reject"
    approver_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(AccessRequest).where(AccessRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if action == "approve":
        req.status = "approved"
        req.approver_id = approver_id
        req.approved_at = datetime.utcnow()
    elif action == "reject":
        req.status = "rejected"
        req.approver_id = approver_id
    else:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    await db.commit()
    await db.refresh(req)
    return {"success": True, "data": AccessRequestResponse.model_validate(req).model_dump(), "errors": []}
