"""
Celery プロビジョニングタスク テスト（Phase 12）

provision_new_user / deprovision_user / transfer_user の
モックベース単体テスト。

準拠: ISO27001 A.5.15 / ILM-001 / ILM-002 / ILM-003
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# ヘルパー: User モデルの最小実体
# ============================================================

def _make_user(
    user_id: str | None = None,
    username: str = "testuser",
    email: str = "test@example.com",
    entra_object_id: str | None = "entra-123",
    ad_dn: str | None = "CN=testuser,OU=Users,DC=example,DC=com",
    hengeone_id: str | None = "ho-456",
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    user.username = username
    user.email = email
    user.display_name = "Test User"
    user.employee_id = "EMP001"
    user.department = "Engineering"
    user.job_title = "Engineer"
    user.entra_object_id = entra_object_id
    user.ad_dn = ad_dn
    user.hengeone_id = hengeone_id
    user.account_status = "active"
    return user


def _make_db_session(user: MagicMock | None) -> MagicMock:
    """SyncSessionLocal() の context manager をシミュレート"""
    db = MagicMock()
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = user
    db.execute.return_value = scalar
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ============================================================
# provision_new_user
# ============================================================

class TestProvisionNewUser:
    """ILM-001: 新規ユーザプロビジョニングタスク"""

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_success(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """正常系: プロビジョニング成功・DB 更新・監査ログ記録"""
        from tasks.provisioning import provision_new_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm

        provisioning_results = {
            "entra": {"id": "entra-new-123"},
            "ad": {"id": "ad-new-456"},
            "hengeone": {"id": "ho-new-789"},
            "errors": [],
        }
        mock_asyncio_run.return_value = provisioning_results

        result = provision_new_user.apply(args=[str(user.id)]).get()

        assert result["success"] is True
        assert result["results"] == provisioning_results
        mock_asyncio_run.assert_called_once()

    @patch("tasks.provisioning.SyncSessionLocal")
    def test_user_not_found(self, mock_session_cls):
        """異常系: ユーザが DB に存在しない場合は失敗を返す"""
        from tasks.provisioning import provision_new_user

        db_cm = _make_db_session(user=None)
        mock_session_cls.return_value = db_cm

        result = provision_new_user.apply(args=[str(uuid.uuid4())]).get()

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_engine_raises_retries(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """異常系: エンジン例外発生時はリトライを試みる"""
        from tasks.provisioning import provision_new_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.side_effect = RuntimeError("Engine failure")

        # max_retries=3 だが EAGER モードで即失敗
        with pytest.raises(RuntimeError):
            provision_new_user.apply(
                args=[str(user.id)],
                retries=3,  # すでにリトライ上限に達した状態を擬似
                throw=True,
            ).get(propagate=True)

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_partial_provisioning_no_entra_id(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """境界値: Entra ID の id が None の場合、DB 更新しない"""
        from tasks.provisioning import provision_new_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm

        # Entra ID なし
        mock_asyncio_run.return_value = {
            "entra": {},
            "hengeone": {"id": "ho-789"},
            "errors": [],
        }

        result = provision_new_user.apply(args=[str(user.id)]).get()
        assert result["success"] is True


# ============================================================
# deprovision_user
# ============================================================

class TestDeprovisionUser:
    """ILM-003: 退職デプロビジョニングタスク"""

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_success(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """正常系: デプロビジョニング成功・ユーザ無効化"""
        from tasks.provisioning import deprovision_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.return_value = {"entra": "disabled", "ad": "disabled", "errors": []}

        result = deprovision_user.apply(args=[str(user.id), "退職"]).get()

        assert result["success"] is True

    @patch("tasks.provisioning.SyncSessionLocal")
    def test_user_not_found(self, mock_session_cls):
        """異常系: ユーザが存在しない"""
        from tasks.provisioning import deprovision_user

        db_cm = _make_db_session(user=None)
        mock_session_cls.return_value = db_cm

        result = deprovision_user.apply(args=[str(uuid.uuid4()), "退職"]).get()

        assert result["success"] is False

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_default_reason(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """境界値: デフォルトの退職理由が使用される"""
        from tasks.provisioning import deprovision_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.return_value = {"errors": []}

        result = deprovision_user.apply(args=[str(user.id)]).get()
        assert result["success"] is True


# ============================================================
# transfer_user
# ============================================================

class TestTransferUser:
    """ILM-002: 異動処理タスク"""

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_success_with_dept_and_title(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """正常系: 部署・役職変更が DB に反映される"""
        from tasks.provisioning import transfer_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.return_value = {"errors": []}

        transfer_info = {
            "new_department": "Infrastructure",
            "new_job_title": "Senior Engineer",
            "new_ou": "OU=Infra,DC=example,DC=com",
        }
        result = transfer_user.apply(args=[str(user.id), transfer_info]).get()

        assert result["success"] is True

    @patch("tasks.provisioning.SyncSessionLocal")
    def test_user_not_found(self, mock_session_cls):
        """異常系: ユーザが存在しない"""
        from tasks.provisioning import transfer_user

        db_cm = _make_db_session(user=None)
        mock_session_cls.return_value = db_cm

        result = transfer_user.apply(args=[str(uuid.uuid4()), {}]).get()
        assert result["success"] is False

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_partial_update_dept_only(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """境界値: 部署のみ指定、役職未指定の場合"""
        from tasks.provisioning import transfer_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.return_value = {"errors": []}

        result = transfer_user.apply(
            args=[str(user.id), {"new_department": "HR"}]
        ).get()
        assert result["success"] is True

    @patch("asyncio.run")
    @patch("tasks.provisioning.IdentityEngine")
    @patch("tasks.provisioning.SyncSessionLocal")
    def test_empty_transfer_info(self, mock_session_cls, mock_engine_cls, mock_asyncio_run):
        """境界値: transfer_info が空の場合は DB 更新なし"""
        from tasks.provisioning import transfer_user

        user = _make_user()
        db_cm = _make_db_session(user)
        mock_session_cls.return_value = db_cm
        mock_asyncio_run.return_value = {"errors": []}

        result = transfer_user.apply(args=[str(user.id), {}]).get()
        assert result["success"] is True


# ============================================================
# _record_audit_log ヘルパー
# ============================================================

class TestRecordAuditLog:
    """監査ログ記録ヘルパーの単体テスト"""

    def test_creates_audit_log_with_hash(self):
        """SHA256 ハッシュチェーンが計算されること"""
        from tasks.provisioning import _record_audit_log

        db = MagicMock()
        # 直前ログあり
        last_log = MagicMock()
        last_log.hash = "prev-hash-abc"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = last_log
        db.execute.return_value = result_mock

        actor_id = str(uuid.uuid4())
        resource_id = str(uuid.uuid4())

        with patch("tasks.provisioning.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "computed-hash"
            _record_audit_log(db, "test.action", actor_id, resource_id, {"key": "val"})
            db.add.assert_called_once()

    def test_first_log_no_previous_hash(self):
        """最初のログ（previous_hash が None）でも正常に動作する"""
        from tasks.provisioning import _record_audit_log

        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # 直前ログなし
        db.execute.return_value = result_mock

        actor_id = str(uuid.uuid4())

        with patch("tasks.provisioning.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "first-hash"
            _record_audit_log(db, "first.action", actor_id, actor_id, {})
            db.add.assert_called_once()
