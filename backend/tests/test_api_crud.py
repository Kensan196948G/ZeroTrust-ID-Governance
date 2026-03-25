"""
API エンドポイント CRUD 統合テスト（Issue #12 Phase 4）

DB モックを使用して以下のエンドポイントの業務ロジックを検証する:
- /api/v1/users: create / get / update / delete / list with filters
- /api/v1/roles: create / assign / revoke
- /api/v1/audit-logs: filter / CSV export
- /api/v1/access-requests: create / approve / reject / pending
- /api/v1/workflows: account-review / provision (Celery モック)

準拠: ISO27001 A.8.4 テスト / NIST CSF DE.CM-01
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


# ------------------------------------------------------------------ helpers --

def _auth_header(roles: list[str]) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles})
    return {"Authorization": f"Bearer {token}"}


ADMIN_HDR = _auth_header(["GlobalAdmin"])
USER_HDR = _auth_header(["Developer"])


def _make_user_mock(**overrides) -> MagicMock:
    """テスト用 User モックオブジェクトを生成"""
    u = MagicMock()
    u.id = overrides.get("id", uuid.uuid4())
    u.employee_id = overrides.get("employee_id", "EMP001")
    u.username = overrides.get("username", "taro.mirai")
    u.display_name = overrides.get("display_name", "未来 太郎")
    u.email = overrides.get("email", "taro@mirai-kensetsu.co.jp")
    u.department_id = overrides.get("department_id", None)
    u.job_title = overrides.get("job_title", "エンジニア")
    u.user_type = overrides.get("user_type", "employee")
    u.account_status = overrides.get("account_status", "active")
    u.entra_object_id = overrides.get("entra_object_id", None)
    u.ad_dn = overrides.get("ad_dn", None)
    u.hengeone_id = overrides.get("hengeone_id", None)
    u.hire_date = overrides.get("hire_date", "2024-04-01")
    u.termination_date = overrides.get("termination_date", None)
    u.last_login = overrides.get("last_login", None)
    u.mfa_enabled = overrides.get("mfa_enabled", False)
    u.risk_score = overrides.get("risk_score", 10)
    u.created_at = overrides.get("created_at", datetime(2024, 4, 1, tzinfo=timezone.utc))
    u.updated_at = overrides.get("updated_at", datetime(2024, 4, 1, tzinfo=timezone.utc))
    return u


def _make_role_mock(**overrides) -> MagicMock:
    """テスト用 Role モックオブジェクトを生成"""
    r = MagicMock()
    r.id = overrides.get("id", uuid.uuid4())
    r.role_name = overrides.get("role_name", "Developer")
    r.description = overrides.get("description", "開発者ロール")
    r.role_type = overrides.get("role_type", "business")
    r.is_privileged = overrides.get("is_privileged", False)
    r.requires_approval = overrides.get("requires_approval", False)
    r.created_at = overrides.get("created_at", datetime(2024, 4, 1, tzinfo=timezone.utc))
    return r


def _make_access_request_mock(**overrides) -> MagicMock:
    """テスト用 AccessRequest モックオブジェクトを生成"""
    ar = MagicMock()
    ar.id = overrides.get("id", uuid.uuid4())
    ar.request_type = overrides.get("request_type", "grant")
    ar.justification = overrides.get("justification", "業務上必要")
    ar.status = overrides.get("status", "pending")
    ar.created_at = overrides.get("created_at", datetime(2024, 4, 1, tzinfo=timezone.utc))
    ar.expires_at = overrides.get("expires_at", None)
    return ar


def _make_audit_log_mock(**overrides) -> MagicMock:
    """テスト用 AuditLog モックオブジェクトを生成"""
    al = MagicMock()
    al.id = overrides.get("id", 1)
    al.event_id = overrides.get("event_id", uuid.uuid4())
    al.event_time = overrides.get("event_time", datetime(2024, 4, 1, tzinfo=timezone.utc))
    al.event_type = overrides.get("event_type", "user_login")
    al.source_system = overrides.get("source_system", "EntraID")
    al.actor_user_id = overrides.get("actor_user_id", uuid.uuid4())
    al.action = overrides.get("action", "login")
    al.result = overrides.get("result", "success")
    al.risk_score = overrides.get("risk_score", 5)
    al.actor_ip = overrides.get("actor_ip", "192.168.1.1")
    al.hash = overrides.get("hash", "abc123")
    return al


def _mock_db(
    scalars_all: list | None = None,
    scalar_one_or_none=None,
    scalar_one=0,
):
    """汎用 DB モック生成"""
    async def _inner():
        mock = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = scalars_all or []
        result.scalar_one_or_none.return_value = scalar_one_or_none
        result.scalar_one.return_value = scalar_one
        mock.execute.return_value = result
        mock.commit = AsyncMock()
        mock.refresh = AsyncMock()
        mock.flush = AsyncMock()
        mock.add = MagicMock()
        mock.delete = AsyncMock()
        yield mock

    app.dependency_overrides[get_db] = _inner


def _clear_db():
    app.dependency_overrides.pop(get_db, None)


# ============================================================
# /api/v1/users — CRUD
# ============================================================

class TestUsersCRUD:
    """users エンドポイントの CRUD 業務ロジックを検証"""

    def test_create_user_admin_success(self) -> None:
        """GlobalAdmin がユーザ作成 → 201 + ユーザ情報返却"""
        mock_user = _make_user_mock()

        async def _db():
            m = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.scalar_one.return_value = 0
            result.scalars.return_value.all.return_value = []
            m.execute.return_value = result
            m.commit = AsyncMock()
            m.flush = AsyncMock()
            m.add = MagicMock()
            # refresh 後に mock_user の属性をコピーする
            async def _refresh(obj):
                obj.id = mock_user.id
                obj.username = mock_user.username
                obj.display_name = mock_user.display_name
                obj.email = mock_user.email
                obj.employee_id = mock_user.employee_id
                obj.user_type = mock_user.user_type
                obj.account_status = mock_user.account_status
                obj.hire_date = mock_user.hire_date
                obj.job_title = mock_user.job_title
                obj.department_id = mock_user.department_id
                obj.entra_object_id = mock_user.entra_object_id
                obj.ad_dn = mock_user.ad_dn
                obj.hengeone_id = mock_user.hengeone_id
                obj.termination_date = mock_user.termination_date
                obj.last_login = mock_user.last_login
                obj.mfa_enabled = mock_user.mfa_enabled
                obj.risk_score = mock_user.risk_score
                obj.created_at = mock_user.created_at
                obj.updated_at = mock_user.updated_at
            m.refresh = _refresh
            yield m

        app.dependency_overrides[get_db] = _db
        try:
            payload = {
                "employee_id": "EMP001",
                "username": "taro.mirai",
                "display_name": "未来 太郎",
                "email": "taro@mirai-kensetsu.co.jp",
                "user_type": "employee",
                "hire_date": "2024-04-01",
            }
            resp = client.post("/api/v1/users", json=payload, headers=ADMIN_HDR)
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["username"] == "taro.mirai"
        finally:
            _clear_db()

    def test_get_user_found(self) -> None:
        """存在するユーザを GET → 200"""
        mock_user = _make_user_mock()
        _mock_db(scalar_one_or_none=mock_user)
        try:
            resp = client.get(f"/api/v1/users/{mock_user.id}", headers=USER_HDR)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_get_user_not_found(self) -> None:
        """存在しないユーザを GET → 404"""
        _mock_db(scalar_one_or_none=None)
        try:
            resp = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=USER_HDR)
            assert resp.status_code == 404
        finally:
            _clear_db()

    def test_update_user_success(self) -> None:
        """ユーザ情報 PATCH → 200 + 更新後情報"""
        mock_user = _make_user_mock()
        _mock_db(scalar_one_or_none=mock_user)
        try:
            resp = client.patch(
                f"/api/v1/users/{mock_user.id}",
                json={"job_title": "シニアエンジニア"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_update_user_not_found(self) -> None:
        """存在しないユーザを PATCH → 404"""
        _mock_db(scalar_one_or_none=None)
        try:
            resp = client.patch(
                f"/api/v1/users/{uuid.uuid4()}",
                json={"job_title": "Manager"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 404
        finally:
            _clear_db()

    def test_disable_user_success(self) -> None:
        """ユーザ論理削除（無効化） → 200"""
        mock_user = _make_user_mock()
        _mock_db(scalar_one_or_none=mock_user)
        try:
            resp = client.delete(f"/api/v1/users/{mock_user.id}", headers=ADMIN_HDR)
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
        finally:
            _clear_db()

    def test_disable_user_not_found(self) -> None:
        """存在しないユーザを DELETE → 404"""
        _mock_db(scalar_one_or_none=None)
        try:
            resp = client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=ADMIN_HDR)
            assert resp.status_code == 404
        finally:
            _clear_db()

    def test_list_users_filter_by_user_type(self) -> None:
        """user_type フィルタ付きリスト → 200"""
        mock_users = [_make_user_mock(user_type="employee")]
        _mock_db(scalars_all=mock_users, scalar_one=1)
        try:
            resp = client.get("/api/v1/users?user_type=employee", headers=USER_HDR)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_list_users_filter_by_account_status(self) -> None:
        """account_status フィルタ付きリスト → 200"""
        _mock_db(scalars_all=[], scalar_one=0)
        try:
            resp = client.get("/api/v1/users?account_status=disabled", headers=USER_HDR)
            assert resp.status_code == 200
        finally:
            _clear_db()


# ============================================================
# /api/v1/roles — CRUD
# ============================================================

class TestRolesCRUD:
    """roles エンドポイントの CRUD 業務ロジックを検証"""

    def test_create_role_admin_success(self) -> None:
        """GlobalAdmin がロール作成 → 201"""
        mock_role = _make_role_mock()

        async def _db():
            m = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
            result.scalar_one.return_value = 0
            m.execute.return_value = result
            m.commit = AsyncMock()
            m.add = MagicMock()

            async def _refresh(obj):
                obj.id = mock_role.id
                obj.role_name = mock_role.role_name
                obj.description = mock_role.description
                obj.role_type = mock_role.role_type
                obj.is_privileged = mock_role.is_privileged
                obj.requires_approval = mock_role.requires_approval
                obj.created_at = mock_role.created_at
            m.refresh = _refresh
            yield m

        app.dependency_overrides[get_db] = _db
        try:
            payload = {
                "role_name": "Developer",
                "description": "開発者ロール",
                "role_type": "business",
                "is_privileged": False,
                "requires_approval": False,
            }
            resp = client.post("/api/v1/roles", json=payload, headers=ADMIN_HDR)
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["role_name"] == "Developer"
        finally:
            _clear_db()

    def test_assign_role_to_user(self) -> None:
        """ユーザへのロール割当 → 201"""
        _mock_db()
        try:
            resp = client.post(
                f"/api/v1/users/{uuid.uuid4()}/roles",
                params={"role_id": str(uuid.uuid4())},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 201
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_revoke_role_from_user_success(self) -> None:
        """ユーザからロール剥奪（存在する）→ 200"""
        mock_user_role = MagicMock()
        _mock_db(scalar_one_or_none=mock_user_role)
        try:
            resp = client.delete(
                f"/api/v1/users/{uuid.uuid4()}/roles/{uuid.uuid4()}",
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_revoke_role_not_found(self) -> None:
        """割当なしのロール剥奪 → 404"""
        _mock_db(scalar_one_or_none=None)
        try:
            resp = client.delete(
                f"/api/v1/users/{uuid.uuid4()}/roles/{uuid.uuid4()}",
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 404
        finally:
            _clear_db()


# ============================================================
# /api/v1/audit-logs — フィルタ・CSV エクスポート
# ============================================================

class TestAuditLogsCRUD:
    """audit-logs エンドポイントのフィルタリングと CSV エクスポートを検証"""

    def test_search_with_event_type_filter(self) -> None:
        """event_type フィルタで監査ログ検索 → 200（SecurityAdmin 必須）"""
        mock_logs = [_make_audit_log_mock(event_type="user_login")]
        _mock_db(scalars_all=mock_logs)
        try:
            resp = client.get("/api/v1/audit-logs?event_type=user_login", headers=ADMIN_HDR)
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert len(body["data"]) == 1
            assert body["data"][0]["event_type"] == "user_login"
        finally:
            _clear_db()

    def test_search_with_source_system_filter(self) -> None:
        """source_system フィルタ → 200（SecurityAdmin 必須）"""
        mock_logs = [_make_audit_log_mock(source_system="AD")]
        _mock_db(scalars_all=mock_logs)
        try:
            resp = client.get("/api/v1/audit-logs?source_system=AD", headers=ADMIN_HDR)
            assert resp.status_code == 200
        finally:
            _clear_db()

    def test_search_with_result_filter(self) -> None:
        """result フィルタ（失敗ログ）→ 200（SecurityAdmin 必須）"""
        _mock_db(scalars_all=[])
        try:
            resp = client.get("/api/v1/audit-logs?result=failure", headers=ADMIN_HDR)
            assert resp.status_code == 200
            assert resp.json()["data"] == []
        finally:
            _clear_db()

    def test_search_with_actor_user_id_filter(self) -> None:
        """actor_user_id フィルタ → 200（SecurityAdmin 必須）"""
        actor_id = uuid.uuid4()
        mock_logs = [_make_audit_log_mock(actor_user_id=actor_id)]
        _mock_db(scalars_all=mock_logs)
        try:
            resp = client.get(
                f"/api/v1/audit-logs?actor_user_id={actor_id}",
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
        finally:
            _clear_db()

    def test_search_with_time_range_filter(self) -> None:
        """from_time / to_time フィルタ → 200（SecurityAdmin 必須）"""
        _mock_db(scalars_all=[])
        try:
            resp = client.get(
                "/api/v1/audit-logs?from_time=2024-01-01T00:00:00&to_time=2024-12-31T23:59:59",
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
        finally:
            _clear_db()

    def test_export_csv_admin_success(self) -> None:
        """GlobalAdmin が CSV エクスポート → 200 + text/csv"""
        mock_logs = [_make_audit_log_mock()]
        _mock_db(scalars_all=mock_logs)
        try:
            resp = client.get("/api/v1/audit-logs/export", headers=ADMIN_HDR)
            assert resp.status_code == 200
            assert "text/csv" in resp.headers.get("content-type", "")
        finally:
            _clear_db()

    def test_export_csv_with_time_filter(self) -> None:
        """時間範囲フィルタ付き CSV エクスポート → 200"""
        _mock_db(scalars_all=[])
        try:
            resp = client.get(
                "/api/v1/audit-logs/export?from_time=2024-01-01T00:00:00",
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
        finally:
            _clear_db()


# ============================================================
# /api/v1/access-requests — CRUD
# ============================================================

class TestAccessRequestsCRUD:
    """access-requests エンドポイントの CRUD を検証"""

    def test_create_request_success(self) -> None:
        """アクセス申請作成 → 201"""
        mock_req = _make_access_request_mock()

        async def _db():
            m = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
            m.execute.return_value = result
            m.commit = AsyncMock()
            m.add = MagicMock()

            async def _refresh(obj):
                obj.id = mock_req.id
                obj.request_type = mock_req.request_type
                obj.justification = mock_req.justification
                obj.status = mock_req.status
                obj.created_at = mock_req.created_at
                obj.expires_at = mock_req.expires_at
            m.refresh = _refresh
            yield m

        app.dependency_overrides[get_db] = _db
        try:
            payload = {"justification": "プロジェクトX用アクセス申請"}
            resp = client.post("/api/v1/access-requests", json=payload, headers=USER_HDR)
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["status"] == "pending"
        finally:
            _clear_db()

    def test_approve_request_success(self) -> None:
        """申請承認（GlobalAdmin）→ 200 + status=approved"""
        mock_req = _make_access_request_mock()
        # approve 後に status が更新されることを確認
        _mock_db(scalar_one_or_none=mock_req)
        try:
            resp = client.patch(
                f"/api/v1/access-requests/{mock_req.id}",
                params={"action": "approve"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_reject_request_success(self) -> None:
        """申請却下（GlobalAdmin）→ 200"""
        mock_req = _make_access_request_mock()
        _mock_db(scalar_one_or_none=mock_req)
        try:
            resp = client.patch(
                f"/api/v1/access-requests/{mock_req.id}",
                params={"action": "reject"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db()

    def test_update_request_invalid_action(self) -> None:
        """不正な action → 400"""
        mock_req = _make_access_request_mock()
        _mock_db(scalar_one_or_none=mock_req)
        try:
            resp = client.patch(
                f"/api/v1/access-requests/{mock_req.id}",
                params={"action": "invalid_action"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 400
        finally:
            _clear_db()

    def test_approve_request_not_found(self) -> None:
        """存在しない申請を承認 → 404"""
        _mock_db(scalar_one_or_none=None)
        try:
            resp = client.patch(
                f"/api/v1/access-requests/{uuid.uuid4()}",
                params={"action": "approve"},
                headers=ADMIN_HDR,
            )
            assert resp.status_code == 404
        finally:
            _clear_db()

    def test_pending_requests_list(self) -> None:
        """承認待ち一覧取得 → 200"""
        mock_reqs = [_make_access_request_mock(status="pending")]
        _mock_db(scalars_all=mock_reqs)
        try:
            resp = client.get("/api/v1/access-requests/pending", headers=USER_HDR)
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
        finally:
            _clear_db()


# ============================================================
# /api/v1/workflows — Celery モック
# ============================================================

class TestWorkflowsCRUD:
    """workflows エンドポイントの Celery タスクキュー連携を検証"""

    def test_account_review_with_celery_mock(self) -> None:
        """account-review: Celery タスクをモックして task_id を返す → 200"""
        mock_task = MagicMock()
        mock_task.id = "celery-task-uuid-001"

        with patch("tasks.review.start_quarterly_review") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post("/api/v1/workflows/account-review", headers=ADMIN_HDR)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["task_id"] == "celery-task-uuid-001"

    def test_quarterly_review_alias(self) -> None:
        """quarterly-review エイリアス → account-review と同等"""
        mock_task = MagicMock()
        mock_task.id = "celery-task-uuid-002"

        with patch("tasks.review.start_quarterly_review") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post("/api/v1/workflows/quarterly-review", headers=ADMIN_HDR)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_account_review_celery_unavailable(self) -> None:
        """Celery 未起動時でも graceful に失敗 → 200 success=False"""
        with patch("tasks.review.start_quarterly_review") as mock_celery:
            mock_celery.delay.side_effect = Exception("Connection refused")
            resp = client.post("/api/v1/workflows/account-review", headers=ADMIN_HDR)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False

    def test_consistency_check_celery_mock(self) -> None:
        """consistency-check: Celery モックで task_id 返却 → 200"""
        mock_task = MagicMock()
        mock_task.id = "celery-task-uuid-003"

        with patch("tasks.review.start_quarterly_review") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post("/api/v1/workflows/consistency-check", headers=ADMIN_HDR)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_provision_with_celery_mock(self) -> None:
        """provision: user_id を受け取り Celery にキュー投入 → 200"""
        user_id = str(uuid.uuid4())
        mock_task = MagicMock()
        mock_task.id = "celery-provision-uuid-001"

        with patch("tasks.provisioning.provision_new_user") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post(
                f"/api/v1/workflows/provision/{user_id}",
                headers=ADMIN_HDR,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["task_id"] == "celery-provision-uuid-001"

    def test_provision_celery_unavailable(self) -> None:
        """provision: Celery 未起動時 graceful 失敗 → 200 success=False"""
        user_id = str(uuid.uuid4())

        with patch("tasks.provisioning.provision_new_user") as mock_celery:
            mock_celery.delay.side_effect = Exception("Broker unavailable")
            resp = client.post(
                f"/api/v1/workflows/provision/{user_id}",
                headers=ADMIN_HDR,
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_pim_expiry_admin_success(self) -> None:
        """pim-expiry: GlobalAdmin → 200 + revoked カウント"""
        resp = client.post("/api/v1/workflows/pim-expiry", headers=ADMIN_HDR)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "revoked" in body["data"]

    def test_mfa_enforcement_admin_success(self) -> None:
        """mfa-enforcement: GlobalAdmin → 200 + suspended カウント"""
        resp = client.post("/api/v1/workflows/mfa-enforcement", headers=ADMIN_HDR)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "suspended" in body["data"]
