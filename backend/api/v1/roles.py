"""ロール管理 API"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.role import Role, UserRole

router = APIRouter()


class RoleCreate(BaseModel):
    role_name: str
    description: str | None = None
    role_type: str = "business"
    is_privileged: bool = False
    requires_approval: bool = False


class RoleResponse(BaseModel):
    id: uuid.UUID
    role_name: str
    role_type: str
    is_privileged: bool
    requires_approval: bool
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("/roles", summary="ロール一覧取得")
async def list_roles(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return {
        "success": True,
        "data": [RoleResponse.model_validate(r).model_dump() for r in roles],
        "meta": {"total": len(roles)},
        "errors": [],
    }


@router.post("/roles", status_code=201, summary="ロール作成")
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)) -> dict:
    role = Role(**payload.model_dump())
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return {"success": True, "data": RoleResponse.model_validate(role).model_dump(), "errors": []}


@router.post("/users/{user_id}/roles", status_code=201, summary="ユーザへのロール割当")
async def assign_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_role = UserRole(user_id=user_id, role_id=role_id)
    db.add(user_role)
    await db.commit()
    return {"success": True, "data": {"message": "Role assigned"}, "errors": []}


@router.delete("/users/{user_id}/roles/{role_id}", summary="ユーザからロール剥奪")
async def revoke_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    await db.delete(user_role)
    await db.commit()
    return {"success": True, "data": {"message": "Role revoked"}, "errors": []}
