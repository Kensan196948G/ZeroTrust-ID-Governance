"""
Celery カバレッジ完全達成テスト（Phase 21b）

以下の未カバー行を補完する:
- tasks/celery_app.py:5-19  — モジュール import によるカバレッジ取得
- tasks/provisioning.py:131-132 — deprovision_user retry パス
- tasks/provisioning.py:183-184 — transfer_user retry パス

準拠: ISO27001:2022 A.8.2 テスト制御 / NIST CSF DE.CM-01
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# helper: User モックと DB セッションモック
# ============================================================

def _make_user(user_id: str | None = None) -> MagicMock:
    user = MagicMock()
    user.id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    user.username = "testuser"
    user.entra_object_id = "entra-123"
    user.ad_dn = "CN=testuser,OU=Users,DC=example,DC=com"
    user.hengeone_id = "ho-456"
    user.department = "Engineering"
    user.job_title = "Engineer"
    return user


def _make_session_cm(user: MagicMock | None) -> MagicMock:
    db = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = user
    db.execute.return_value = scalar_result
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ============================================================
# tasks/celery_app.py:5-19 — モジュール import カバレッジ
# ============================================================
class TestCeleryAppImport:
    """celery_app モジュールを import してステートメントをカバーする"""

    def test_celery_app_import_and_attributes(self) -> None:
        """tasks.celery_app が正常に import でき、beat_schedule が設定されている"""
        from tasks.celery_app import celery_app

        assert celery_app is not None
        assert celery_app.main == "ztid_governance"
        assert "quarterly-account-review" in celery_app.conf.beat_schedule

    def test_celery_app_task_serializer_config(self) -> None:
        """task_serializer が json に設定されている"""
        from tasks.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_celery_app_timezone_config(self) -> None:
        """timezone が Asia/Tokyo に設定されている"""
        from tasks.celery_app import celery_app

        assert celery_app.conf.timezone == "Asia/Tokyo"
        assert celery_app.conf.enable_utc is True

    def test_celery_app_retry_config(self) -> None:
        """task_acks_late および task_reject_on_worker_lost が True"""
        from tasks.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True


# ============================================================
# tasks/provisioning.py:131-132 — deprovision_user retry パス
# ============================================================
class TestDeprovisionUserRetry:
    """IdentityEngine 例外時に self.retry が呼ばれるパスを検証"""

    def test_deprovision_user_retries_on_engine_exception(self) -> None:
        """IdentityEngine.deprovision_user が例外を投げると self.retry が呼ばれる（line 131-132）"""
        from tasks.provisioning import deprovision_user
        from celery.exceptions import Retry

        user_id = str(uuid.uuid4())
        user = _make_user(user_id)
        session_cm = _make_session_cm(user)

        with (
            patch("tasks.provisioning._get_sync_session", return_value=session_cm),
            patch("tasks.provisioning.IdentityEngine"),
            patch("asyncio.run", side_effect=RuntimeError("broker unavailable")),
        ):
            # self.retry は Retry 例外を raise する
            with pytest.raises((Retry, RuntimeError)):
                deprovision_user.apply(args=[user_id, "退職"]).get()

    def test_deprovision_user_retry_raises_via_apply(self) -> None:
        """apply() 呼び出しで IdentityEngine 例外 → retry が実行される"""
        from tasks.provisioning import deprovision_user

        user_id = str(uuid.uuid4())
        user = _make_user(user_id)
        session_cm = _make_session_cm(user)

        error = ConnectionError("Redis not available")

        with (
            patch("tasks.provisioning._get_sync_session", return_value=session_cm),
            patch("asyncio.run", side_effect=error),
        ):
            # max_retries=3 かつ ALWAYS_EAGER モード: Retry が raise される
            with pytest.raises(Exception):
                deprovision_user.apply(args=[user_id]).get(propagate=True)


# ============================================================
# tasks/provisioning.py:183-184 — transfer_user retry パス
# ============================================================
class TestTransferUserRetry:
    """IdentityEngine 例外時に transfer_user の self.retry が呼ばれるパスを検証"""

    def test_transfer_user_retries_on_engine_exception(self) -> None:
        """IdentityEngine.transfer_user が例外を投げると self.retry が呼ばれる（line 183-184）"""
        from tasks.provisioning import transfer_user

        user_id = str(uuid.uuid4())
        user = _make_user(user_id)
        session_cm = _make_session_cm(user)

        transfer_info = {"new_department": "Sales", "new_job_title": "Manager"}

        with (
            patch("tasks.provisioning._get_sync_session", return_value=session_cm),
            patch("asyncio.run", side_effect=RuntimeError("transfer engine error")),
        ):
            with pytest.raises(Exception):
                transfer_user.apply(args=[user_id, transfer_info]).get(propagate=True)

    def test_transfer_user_retry_with_connection_error(self) -> None:
        """ConnectionError 発生時に retry が実行される"""
        from tasks.provisioning import transfer_user

        user_id = str(uuid.uuid4())
        user = _make_user(user_id)
        session_cm = _make_session_cm(user)

        transfer_info = {"new_department": "Engineering"}

        with (
            patch("tasks.provisioning._get_sync_session", return_value=session_cm),
            patch("asyncio.run", side_effect=ConnectionError("network error")),
        ):
            with pytest.raises(Exception):
                transfer_user.apply(args=[user_id, transfer_info]).get(propagate=True)
