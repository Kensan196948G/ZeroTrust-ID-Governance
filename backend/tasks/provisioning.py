"""
プロビジョニング Celery タスク
新規入社・退職・異動のアカウントライフサイクル管理
設計仕様書 7.1 準拠（ILM-001, ILM-002, ILM-003）
"""

import logging
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

from core.database import SyncSessionLocal  # 同期セッション（Celery ワーカー用）
from engine.identity_engine import IdentityEngine
from models.audit_log import AuditLog
from models.user import User

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Celery タスク用同期 DB セッション"""
    return SyncSessionLocal()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60秒後にリトライ
    name="tasks.provisioning.provision_new_user",
)
def provision_new_user(self, user_id: str) -> dict:
    """
    新規ユーザプロビジョニングタスク（ILM-001）

    EntraID / AD / HENGEONE の順にアカウントを作成する。
    いずれかが失敗した場合でも、成功したシステムの ID を
    DB に保存して部分的な状態を記録する。
    """
    import asyncio

    logger.info("Provisioning task started", extra={"user_id": user_id})

    with _get_sync_session() as db:
        # ユーザデータ取得
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user:
            logger.error("User not found for provisioning", extra={"user_id": user_id})
            return {"success": False, "error": "User not found"}

        user_data = {
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "employee_id": user.employee_id,
            "department": user.department,
            "job_title": user.job_title,
        }

    # 非同期エンジンを同期コンテキストで実行
    try:
        engine = IdentityEngine()
        results = asyncio.run(engine.provision_user(user_data))
    except Exception as exc:
        logger.error("Provisioning failed", extra={"user_id": user_id, "error": str(exc)})
        raise self.retry(exc=exc)

    # DB 更新: 各システムの ID を保存
    with _get_sync_session() as db:
        update_values: dict = {}

        if results.get("entra") and results["entra"].get("id"):
            update_values["entra_object_id"] = results["entra"]["id"]

        if results.get("hengeone") and results["hengeone"].get("id"):
            update_values["hengeone_id"] = results["hengeone"]["id"]

        if update_values:
            db.execute(
                update(User).where(User.id == uuid.UUID(user_id)).values(**update_values)
            )

        # 監査ログ記録
        _record_audit_log(
            db,
            action="user.provisioned",
            actor_id=user_id,
            resource_id=user_id,
            details={
                "systems": list(results.keys()),
                "errors": results.get("errors", []),
            },
        )
        db.commit()

    logger.info("Provisioning task completed", extra={"user_id": user_id})
    return {"success": True, "results": results}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.provisioning.deprovision_user",
)
def deprovision_user(self, user_id: str, reason: str = "退職") -> dict:
    """
    ユーザ退職処理タスク（ILM-003）

    3システムのアカウントを即時無効化する。
    """
    import asyncio

    logger.info("Deprovisioning task started", extra={"user_id": user_id})

    with _get_sync_session() as db:
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user:
            return {"success": False, "error": "User not found"}

        user_data = {
            "entra_object_id": user.entra_object_id,
            "ad_dn": user.ad_dn,
            "hengeone_id": user.hengeone_id,
        }

    try:
        engine = IdentityEngine()
        results = asyncio.run(engine.deprovision_user(user_data))
    except Exception as exc:
        raise self.retry(exc=exc)

    # ユーザを無効化
    with _get_sync_session() as db:
        db.execute(
            update(User).where(User.id == uuid.UUID(user_id)).values(is_active=False)
        )

        _record_audit_log(
            db,
            action="user.deprovisioned",
            actor_id=user_id,
            resource_id=user_id,
            details={"reason": reason, "errors": results.get("errors", [])},
        )
        db.commit()

    logger.info("Deprovisioning task completed", extra={"user_id": user_id})
    return {"success": True, "results": results}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.provisioning.transfer_user",
)
def transfer_user(self, user_id: str, transfer_info: dict) -> dict:
    """
    異動処理タスク（ILM-002）

    transfer_info:
      - new_department: 新部署
      - new_job_title: 新役職
      - new_ou: AD の新 OU
    """
    import asyncio

    with _get_sync_session() as db:
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user:
            return {"success": False, "error": "User not found"}

        user_data = {
            "entra_object_id": user.entra_object_id,
            "ad_dn": user.ad_dn,
        }

    try:
        engine = IdentityEngine()
        results = asyncio.run(engine.transfer_user(user_data, transfer_info))
    except Exception as exc:
        raise self.retry(exc=exc)

    with _get_sync_session() as db:
        update_values = {}
        if new_dept := transfer_info.get("new_department"):
            update_values["department"] = new_dept
        if new_title := transfer_info.get("new_job_title"):
            update_values["job_title"] = new_title

        if update_values:
            db.execute(
                update(User).where(User.id == uuid.UUID(user_id)).values(**update_values)
            )

        _record_audit_log(
            db,
            action="user.transferred",
            actor_id=user_id,
            resource_id=user_id,
            details={"transfer_info": transfer_info, "errors": results.get("errors", [])},
        )
        db.commit()

    return {"success": True, "results": results}


# ------------------------------------------------------------------
# ヘルパー
# ------------------------------------------------------------------

def _record_audit_log(
    db,
    action: str,
    actor_id: str,
    resource_id: str,
    details: dict,
) -> None:
    """監査ログを同期セッションに追加する"""
    # 直前のログの hash を取得してチェーンを繋ぐ
    last_log = db.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
    ).scalar_one_or_none()
    previous_hash = last_log.hash if last_log else None

    log_entry = {
        "action": action,
        "actor_id": actor_id,
        "resource_id": resource_id,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit_log = AuditLog(
        event_type="identity.lifecycle",
        source_system="celery",
        action=action,
        actor_user_id=uuid.UUID(actor_id),
        target_resource=resource_id,
        result="success",
        details=details,
        hash=AuditLog.compute_hash(log_entry, previous_hash),
    )
    db.add(audit_log)
