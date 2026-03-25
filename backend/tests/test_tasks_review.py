"""
Celery 棚卸タスク テスト（Phase 12）

start_quarterly_review / _is_consistent の
モックベース単体テスト。

準拠: ISO27001 A.5.15 / ILM-005 / GOV-004
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


# ============================================================
# ヘルパー
# ============================================================

def _make_user(user_id: str | None = None, username: str = "reviewer") -> MagicMock:
    user = MagicMock()
    user.id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    user.username = username
    user.account_status = "active"
    user.entra_object_id = "entra-123"
    user.ad_dn = "CN=reviewer,DC=example,DC=com"
    user.hengeone_id = "ho-456"
    return user


def _make_role_assignment(expired: bool = False) -> MagicMock:
    role = MagicMock()
    role.user_id = uuid.uuid4()
    role.role_id = uuid.uuid4()
    if expired:
        role.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        role.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    return role


def _build_db_session(users: list, roles: list, expired_roles: list) -> MagicMock:
    """SyncSessionLocal() を完全モック"""
    db = MagicMock()

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = users

    roles_result = MagicMock()
    roles_result.scalars.return_value.all.return_value = roles

    expired_result = MagicMock()
    expired_result.scalars.return_value.all.return_value = expired_roles

    last_log_result = MagicMock()
    last_log_result.scalar_one_or_none.return_value = None

    # execute の呼び出し順に応じた return 値
    db.execute.side_effect = [
        users_result,      # 1回目: ユーザ一覧
        expired_result,    # 2回目: 期限切れロール
        roles_result,      # 3回目: ユーザロール一覧（SoD チェック用）
        last_log_result,   # 4回目以降: 監査ログ
        MagicMock(),       # 追加呼び出し分の余裕
    ]

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ============================================================
# start_quarterly_review
# ============================================================

class TestStartQuarterlyReview:
    """ILM-005: 四半期アカウント棚卸タスク"""

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_no_users(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """境界値: アクティブユーザが0件の場合、空の結果を返す"""
        from tasks.review import start_quarterly_review

        db = MagicMock()
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []
        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [users_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-0"
            result = start_quarterly_review.apply().get()

        assert result["reviewed_users"] == 0
        assert result["inconsistencies"] == []
        assert result["expired_roles_removed"] == 0
        assert result["sod_violations"] == []

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_consistent_user_no_issues(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """正常系: 整合性あり・期限切れロールなし・SoD違反なし"""
        from tasks.review import start_quarterly_review

        user = _make_user()
        db = MagicMock()

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = []

        roles_result = MagicMock()
        roles_result.scalars.return_value.all.return_value = []

        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [users_result, expired_result, roles_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        # 整合性あり
        mock_asyncio_run.return_value = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        mock_pe_cls.return_value.check_sod_violations.return_value = []

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-ok"
            result = start_quarterly_review.apply().get()

        assert result["reviewed_users"] == 1
        assert result["inconsistencies"] == []
        assert result["expired_roles_removed"] == 0
        assert result["sod_violations"] == []

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_inconsistent_user_detected(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """正常系: 整合性なしユーザが inconsistencies に追加される"""
        from tasks.review import start_quarterly_review

        user = _make_user()
        db = MagicMock()

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = []

        roles_result = MagicMock()
        roles_result.scalars.return_value.all.return_value = []

        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [users_result, expired_result, roles_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        # Entra ID が非アクティブ → 不整合
        mock_asyncio_run.return_value = {
            "entra": {"exists": True, "active": False},
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        mock_pe_cls.return_value.check_sod_violations.return_value = []

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-inc"
            result = start_quarterly_review.apply().get()

        assert result["reviewed_users"] == 1
        assert len(result["inconsistencies"]) == 1
        assert result["inconsistencies"][0]["username"] == user.username

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_expired_roles_removed(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """正常系: 期限切れロールが削除され expired_roles_removed がカウントされる"""
        from tasks.review import start_quarterly_review

        user = _make_user()
        expired_role = _make_role_assignment(expired=True)
        db = MagicMock()

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = [expired_role]

        roles_result = MagicMock()
        roles_result.scalars.return_value.all.return_value = []

        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [users_result, expired_result, roles_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        mock_asyncio_run.return_value = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        mock_pe_cls.return_value.check_sod_violations.return_value = []

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-expired"
            result = start_quarterly_review.apply().get()

        assert result["expired_roles_removed"] == 1
        db.delete.assert_called_once_with(expired_role)

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_sod_violation_detected(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """正常系: SoD 違反が sod_violations に追加される"""
        from tasks.review import start_quarterly_review

        user = _make_user()
        role_assign = _make_role_assignment()
        db = MagicMock()

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = []

        roles_result = MagicMock()
        roles_result.scalars.return_value.all.return_value = [role_assign]

        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [users_result, expired_result, roles_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        mock_asyncio_run.return_value = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        # SoD 違反を注入
        mock_pe_cls.return_value.check_sod_violations.return_value = [
            ("RoleA", "RoleB")
        ]

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-sod"
            result = start_quarterly_review.apply().get()

        assert len(result["sod_violations"]) == 1
        assert result["sod_violations"][0]["username"] == user.username
        assert "RoleA × RoleB" in result["sod_violations"][0]["violations"]

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_consistency_check_exception_is_swallowed(
        self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run
    ):
        """境界値: 整合性チェックが例外を投げても処理を継続する"""
        from tasks.review import start_quarterly_review

        user = _make_user()
        db = MagicMock()

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = []

        roles_result = MagicMock()
        roles_result.scalars.return_value.all.return_value = []

        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [users_result, expired_result, roles_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        # 整合性チェックで例外
        mock_asyncio_run.side_effect = ConnectionError("External system unreachable")
        mock_pe_cls.return_value.check_sod_violations.return_value = []

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-exc"
            result = start_quarterly_review.apply().get()

        # 例外があっても処理は完了する
        assert result["reviewed_users"] == 1
        assert "completed_at" in result

    @patch("asyncio.run")
    @patch("tasks.review.PolicyEngine")
    @patch("tasks.review.IdentityEngine")
    @patch("tasks.review.SyncSessionLocal")
    def test_result_has_timestamps(self, mock_session_cls, mock_ie_cls, mock_pe_cls, mock_asyncio_run):
        """結果に started_at / completed_at が含まれること"""
        from tasks.review import start_quarterly_review

        db = MagicMock()
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []
        last_log_result = MagicMock()
        last_log_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [users_result, last_log_result]

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = cm

        with patch("tasks.review.AuditLog.compute_hash") as mock_audit_cls:
            mock_audit_cls.return_value = "hash-ts"
            result = start_quarterly_review.apply().get()

        assert "started_at" in result
        assert "completed_at" in result


# ============================================================
# _is_consistent
# ============================================================

class TestIsConsistent:
    """整合性判定ヘルパーの単体テスト"""

    def test_all_systems_exist_and_active(self):
        """正常系: 3システム全て存在・アクティブ → True"""
        from tasks.review import _is_consistent

        consistency = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        assert _is_consistent(consistency) is True

    def test_one_system_not_active(self):
        """異常系: いずれか1システムが非アクティブ → False"""
        from tasks.review import _is_consistent

        consistency = {
            "entra": {"exists": True, "active": False},  # ← 非アクティブ
            "ad": {"exists": True, "active": True},
            "hengeone": {"exists": True, "active": True},
        }
        assert _is_consistent(consistency) is False

    def test_one_system_not_exists(self):
        """異常系: いずれか1システムが存在しない → False"""
        from tasks.review import _is_consistent

        consistency = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": False, "active": True},  # ← 存在しない
            "hengeone": {"exists": True, "active": True},
        }
        assert _is_consistent(consistency) is False

    def test_system_missing_from_dict(self):
        """境界値: システムキー自体が欠落 → False"""
        from tasks.review import _is_consistent

        # hengeone が欠落
        consistency = {
            "entra": {"exists": True, "active": True},
            "ad": {"exists": True, "active": True},
        }
        assert _is_consistent(consistency) is False

    def test_empty_consistency(self):
        """境界値: 空の consistency dict → False"""
        from tasks.review import _is_consistent

        assert _is_consistent({}) is False

    def test_all_systems_inactive(self):
        """境界値: 全システム非アクティブ → False"""
        from tasks.review import _is_consistent

        consistency = {
            "entra": {"exists": True, "active": False},
            "ad": {"exists": True, "active": False},
            "hengeone": {"exists": True, "active": False},
        }
        assert _is_consistent(consistency) is False
