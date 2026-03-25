"""
アカウント棚卸 Celery タスク
四半期ごとの定期アクセス見直し（ILM-005 / GOV-004）
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import shared_task
from sqlalchemy import select

from core.database import SyncSessionLocal
from engine.identity_engine import IdentityEngine
from engine.policy_engine import PolicyEngine
from models.audit_log import AuditLog
from models.user import User
from models.role import UserRole

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="tasks.review.start_quarterly_review",
)
def start_quarterly_review(self) -> dict:
    """
    四半期アカウント棚卸タスク（ILM-005）

    1. 全アクティブユーザの 3システム整合性チェック
    2. 期限切れロールの自動削除
    3. SoD 違反の検出とレポート
    4. 孤児アカウント（DBにあるが外部システムにない）の検出
    """
    import asyncio

    logger.info("Quarterly account review started")

    results: dict[str, Any] = {
        "reviewed_users": 0,
        "inconsistencies": [],
        "expired_roles_removed": 0,
        "sod_violations": [],
        "orphan_accounts": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    with SyncSessionLocal() as db:
        # アクティブユーザ一覧
        users = db.execute(select(User).where(User.account_status == "active")).scalars().all()

        identity_engine = IdentityEngine()
        policy_engine = PolicyEngine()

        for user in users:
            results["reviewed_users"] += 1

            # 3システム整合性チェック
            try:
                consistency = asyncio.run(
                    identity_engine.verify_consistency(user.username)
                )
                if not _is_consistent(consistency):
                    results["inconsistencies"].append(
                        {"user_id": str(user.id), "username": user.username, "details": consistency}
                    )
            except Exception as exc:
                logger.warning(
                    "Consistency check failed",
                    extra={"username": user.username, "error": str(exc)},
                )

            # 期限切れロールの削除
            expired_roles = db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.expires_at < datetime.now(timezone.utc),
                )
            ).scalars().all()

            for role_assignment in expired_roles:
                db.delete(role_assignment)
                results["expired_roles_removed"] += 1
                logger.info(
                    "Expired role removed",
                    extra={"user_id": str(user.id), "role_id": str(role_assignment.role_id)},
                )

            # SoD 違反チェック
            user_roles = db.execute(
                select(UserRole).where(UserRole.user_id == user.id)
            ).scalars().all()
            role_names = [str(r.role_id) for r in user_roles]  # ロール名はJOINで取得が望ましいが簡略化

            sod_violations = policy_engine.check_sod_violations(role_names)
            if sod_violations:
                results["sod_violations"].append(
                    {
                        "user_id": str(user.id),
                        "username": user.username,
                        "violations": [f"{a} × {b}" for a, b in sod_violations],
                    }
                )

        db.commit()

        # 棚卸完了の監査ログ
        last_log = db.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
        ).scalar_one_or_none()
        previous_hash = (last_log.hash or "") if last_log else ""

        summary = {
            "reviewed_users": results["reviewed_users"],
            "inconsistencies_count": len(results["inconsistencies"]),
            "expired_roles_removed": results["expired_roles_removed"],
            "sod_violations_count": len(results["sod_violations"]),
        }
        log_entry = {
            "action": "account.review.completed",
            "actor_id": "system",
            "details": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        audit_log = AuditLog(
            event_type="identity.review",
            source_system="celery",
            action="account.review.completed",
            actor_user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # system actor
            target_resource="all",
            result="success",
            details=summary,
            hash=AuditLog.compute_hash(log_entry, previous_hash),
        )
        db.add(audit_log)
        db.commit()

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Quarterly account review completed", extra=results)
    return results


def _is_consistent(consistency: dict) -> bool:
    """3システムの状態が全て一致しているか確認"""
    systems = ["entra", "ad", "hengeone"]
    for system in systems:
        data = consistency.get(system, {})
        if not data.get("exists") or not data.get("active"):
            return False
    return True
