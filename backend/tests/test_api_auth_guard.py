"""
API エンドポイント認証ガード統合テスト

各ルーターに適用した JWT 認証 / ロール認可を検証する。
- 認証なし → 401 Unauthorized
- 認証あり・権限不足 → 403 Forbidden
- GlobalAdmin → 正常系（DB モック）

準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-01
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


# ------------------------------------------------------------------ helpers --

def _auth_header(roles: list[str], user_id: str | None = None) -> dict[str, str]:
    """指定ロール付き JWT ヘッダーを生成"""
    uid = user_id or str(uuid.uuid4())
    token = create_access_token(uid, extra_claims={"roles": roles})
    return {"Authorization": f"Bearer {token}"}


ADMIN_HDR = _auth_header(["GlobalAdmin"])
USER_HDR = _auth_header(["Developer"])  # GlobalAdmin でない一般ロール


def _mock_db_override():
    """空結果を返す非同期 DB セッションのモック"""
    async def _inner():
        mock = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.scalar_one.return_value = 0
        mock.execute.return_value = result
        mock.commit = AsyncMock()
        mock.refresh = AsyncMock()
        mock.add = MagicMock()
        mock.delete = AsyncMock()
        yield mock

    app.dependency_overrides[get_db] = _inner


def _clear_db_override():
    app.dependency_overrides.pop(get_db, None)


# ============================================================
# /api/v1/users — 認証ガード
# ============================================================

class TestUsersAuthGuard:
    """users エンドポイントの認証・認可を検証"""

    def test_list_users_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 401

    def test_get_user_no_auth_returns_401(self) -> None:
        resp = client.get(f"/api/v1/users/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_create_user_no_auth_returns_401(self) -> None:
        resp = client.post("/api/v1/users", json={})
        assert resp.status_code == 401

    def test_update_user_no_auth_returns_401(self) -> None:
        resp = client.patch(f"/api/v1/users/{uuid.uuid4()}", json={})
        assert resp.status_code == 401

    def test_delete_user_no_auth_returns_401(self) -> None:
        resp = client.delete(f"/api/v1/users/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_create_user_non_admin_returns_403(self) -> None:
        """GlobalAdmin でないトークンでユーザ作成 → 403"""
        resp = client.post("/api/v1/users", json={}, headers=USER_HDR)
        assert resp.status_code == 403

    def test_update_user_non_admin_returns_403(self) -> None:
        resp = client.patch(f"/api/v1/users/{uuid.uuid4()}", json={}, headers=USER_HDR)
        assert resp.status_code == 403

    def test_delete_user_non_admin_returns_403(self) -> None:
        resp = client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=USER_HDR)
        assert resp.status_code == 403

    def test_list_users_with_auth_reaches_endpoint(self) -> None:
        """認証済みユーザはユーザ一覧エンドポイントに到達できる（DB モック）"""
        _mock_db_override()
        try:
            resp = client.get("/api/v1/users", headers=USER_HDR)
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["data"] == []
        finally:
            _clear_db_override()

    def test_get_user_with_auth_not_found(self) -> None:
        """認証済み・存在しないユーザ → 404（DB モック）"""
        _mock_db_override()
        try:
            resp = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=USER_HDR)
            assert resp.status_code == 404
        finally:
            _clear_db_override()


# ============================================================
# /api/v1/roles — 認証ガード
# ============================================================

class TestRolesAuthGuard:
    """roles エンドポイントの認証・認可を検証"""

    def test_list_roles_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/roles")
        assert resp.status_code == 401

    def test_create_role_no_auth_returns_401(self) -> None:
        resp = client.post("/api/v1/roles", json={})
        assert resp.status_code == 401

    def test_assign_role_no_auth_returns_401(self) -> None:
        resp = client.post(f"/api/v1/users/{uuid.uuid4()}/roles")
        assert resp.status_code == 401

    def test_revoke_role_no_auth_returns_401(self) -> None:
        resp = client.delete(f"/api/v1/users/{uuid.uuid4()}/roles/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_create_role_non_admin_returns_403(self) -> None:
        resp = client.post("/api/v1/roles", json={}, headers=USER_HDR)
        assert resp.status_code == 403

    def test_assign_role_non_admin_returns_403(self) -> None:
        resp = client.post(
            f"/api/v1/users/{uuid.uuid4()}/roles",
            params={"role_id": str(uuid.uuid4())},
            headers=USER_HDR,
        )
        assert resp.status_code == 403

    def test_revoke_role_non_admin_returns_403(self) -> None:
        resp = client.delete(
            f"/api/v1/users/{uuid.uuid4()}/roles/{uuid.uuid4()}",
            headers=USER_HDR,
        )
        assert resp.status_code == 403

    def test_list_roles_with_auth_reaches_endpoint(self) -> None:
        """認証済みユーザはロール一覧に到達できる（DB モック）"""
        _mock_db_override()
        try:
            resp = client.get("/api/v1/roles", headers=USER_HDR)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db_override()


# ============================================================
# /api/v1/audit-logs — 認証ガード
# ============================================================

class TestAuditAuthGuard:
    """audit-logs エンドポイントの認証・認可を検証"""

    def test_search_audit_logs_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 401

    def test_export_audit_logs_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/audit-logs/export")
        assert resp.status_code == 401

    def test_export_audit_logs_non_admin_returns_403(self) -> None:
        resp = client.get("/api/v1/audit-logs/export", headers=USER_HDR)
        assert resp.status_code == 403

    def test_search_audit_logs_with_auth_reaches_endpoint(self) -> None:
        """SecurityAdmin は監査ログ検索に到達できる（DB モック）"""
        _mock_db_override()
        try:
            resp = client.get("/api/v1/audit-logs", headers=ADMIN_HDR)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db_override()


# ============================================================
# /api/v1/access-requests — 認証ガード
# ============================================================

class TestAccessRequestAuthGuard:
    """access-requests エンドポイントの認証・認可を検証"""

    def test_list_requests_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/access-requests")
        assert resp.status_code == 401

    def test_create_request_no_auth_returns_401(self) -> None:
        resp = client.post("/api/v1/access-requests", json={"justification": "test"})
        assert resp.status_code == 401

    def test_pending_requests_no_auth_returns_401(self) -> None:
        resp = client.get("/api/v1/access-requests/pending")
        assert resp.status_code == 401

    def test_update_request_no_auth_returns_401(self) -> None:
        resp = client.patch(f"/api/v1/access-requests/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_update_request_non_admin_returns_403(self) -> None:
        """申請承認は GlobalAdmin のみ可"""
        resp = client.patch(
            f"/api/v1/access-requests/{uuid.uuid4()}",
            params={"action": "approve"},
            headers=USER_HDR,
        )
        assert resp.status_code == 403

    def test_list_requests_with_auth_reaches_endpoint(self) -> None:
        """認証済みユーザはアクセス申請一覧に到達できる（DB モック）"""
        _mock_db_override()
        try:
            resp = client.get("/api/v1/access-requests", headers=USER_HDR)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            _clear_db_override()


# ============================================================
# /api/v1/workflows — 認証ガード
# ============================================================

class TestWorkflowsAuthGuard:
    """workflows エンドポイントの認証・認可を検証（全て GlobalAdmin 要件）"""

    WORKFLOW_ENDPOINTS = [
        "/api/v1/workflows/account-review",
        "/api/v1/workflows/quarterly-review",
        "/api/v1/workflows/consistency-check",
        "/api/v1/workflows/risk-scan",
        "/api/v1/workflows/pim-expiry",
        "/api/v1/workflows/mfa-enforcement",
    ]

    @pytest.mark.parametrize("endpoint", WORKFLOW_ENDPOINTS)
    def test_workflow_no_auth_returns_401(self, endpoint: str) -> None:
        resp = client.post(endpoint)
        assert resp.status_code == 401

    @pytest.mark.parametrize("endpoint", WORKFLOW_ENDPOINTS)
    def test_workflow_non_admin_returns_403(self, endpoint: str) -> None:
        resp = client.post(endpoint, headers=USER_HDR)
        assert resp.status_code == 403

    def test_provision_no_auth_returns_401(self) -> None:
        resp = client.post(f"/api/v1/workflows/provision/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_provision_non_admin_returns_403(self) -> None:
        resp = client.post(
            f"/api/v1/workflows/provision/{uuid.uuid4()}",
            headers=USER_HDR,
        )
        assert resp.status_code == 403

    def test_risk_scan_admin_reaches_endpoint(self) -> None:
        """GlobalAdmin はワークフロー実行エンドポイントに到達できる"""
        resp = client.post("/api/v1/workflows/risk-scan", headers=ADMIN_HDR)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
