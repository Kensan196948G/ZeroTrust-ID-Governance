"""
ユーザ管理 API
設計仕様書 3.1 ユーザ管理 API エンドポイントに準拠

準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-05 アクセス権限管理
"""

import uuid
from datetime import date, datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import CurrentUser, get_current_user, require_any_role, require_role
from core.database import get_db
from models.user import User

router = APIRouter()


# --- Pydantic スキーマ ---

class UserType(str, Enum):
    """ユーザ種別 — ISO27001 A.5.15 アクセス制御ポリシー"""
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    PARTNER = "partner"
    ADMIN = "admin"


class UserCreate(BaseModel):
    """ユーザ作成リクエスト — 入力バリデーション強化（NIST CSF PR.AA-05）"""
    employee_id: str = Field(min_length=1, max_length=20)
    username: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="英数字・ドット・ハイフン・アンダーバーのみ許可",
    )
    display_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(default=None, max_length=200)
    user_type: UserType = UserType.EMPLOYEE
    hire_date: date  # ISO 8601 形式を自動検証（YYYY-MM-DD）


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    department_id: uuid.UUID | None = None
    account_status: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    employee_id: str
    username: str
    display_name: str
    email: str
    user_type: str
    account_status: str
    mfa_enabled: bool
    risk_score: int
    hire_date: date  # DB の date 型と整合（JSON シリアライズ時に ISO 文字列へ変換）
    created_at: datetime

    model_config = {"from_attributes": True}


def _build_response(success: bool, data, meta: dict | None = None) -> dict:
    return {"success": success, "data": data, "meta": meta or {}, "errors": []}


# --- エンドポイント ---

@router.get("/users", summary="ユーザ一覧取得")
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user_type: str | None = Query(default=None),
    account_status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_any_role("Developer", "Approver", "SecurityAdmin", "GlobalAdmin")
    ),
) -> dict:
    """全ユーザ一覧を取得（ページネーション付き）"""
    query = select(User)
    if user_type:
        query = query.where(User.user_type == user_type)
    if account_status:
        query = query.where(User.account_status == account_status)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    return _build_response(
        True,
        [UserResponse.model_validate(u).model_dump() for u in users],
        {"total": total, "page": page, "per_page": per_page},
    )


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="ユーザ作成（プロビジョニング）")
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("GlobalAdmin")),
) -> dict:
    """新規ユーザを作成し、非同期プロビジョニングタスクをキュー投入"""
    user = User(
        employee_id=payload.employee_id,
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        department_id=payload.department_id,
        job_title=payload.job_title,
        user_type=payload.user_type.value,
        hire_date=payload.hire_date,  # Pydantic が date 型で受け取るので変換不要
    )
    db.add(user)
    await db.flush()

    # 非同期プロビジョニングタスクをキュー投入
    try:
        from tasks.provisioning import provision_new_user
        provision_new_user.delay(str(user.id))
    except Exception:
        pass  # タスクキュー未起動時はスキップ

    await db.commit()
    await db.refresh(user)
    return _build_response(True, UserResponse.model_validate(user).model_dump())


@router.get("/users/{user_id}", summary="ユーザ詳細取得")
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _build_response(True, UserResponse.model_validate(user).model_dump())


@router.patch("/users/{user_id}", summary="ユーザ情報更新")
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("GlobalAdmin")),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return _build_response(True, UserResponse.model_validate(user).model_dump())


@router.delete("/users/{user_id}", summary="ユーザ無効化（論理削除）")
async def disable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("GlobalAdmin")),
) -> dict:
    """退職処理：アカウントを無効化（物理削除は行わない）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.account_status = "disabled"

    # デプロビジョニングタスクをキュー投入
    try:
        from tasks.provisioning import deprovision_user
        deprovision_user.delay(str(user.id))
    except Exception:
        pass

    await db.commit()
    return _build_response(True, {"message": f"User {user.username} has been disabled"})
