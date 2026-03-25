"""
RBAC 細粒化テスト（Phase 8）

検証項目:
- GET /api/v1/users: Developer以上のみ → Viewer は 403
- GET /api/v1/audit-logs: SecurityAdmin/GlobalAdmin のみ → Developer は 403
- 適切なロール → 200 OK

準拠: ISO27001 A.5.15 / NIST CSF PR.AA-05
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


def _token(roles: list[str]) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles})
    return {"Authorization": f"Bearer {token}"}


def _mock_db():
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
        yield mock

    app.dependency_overrides[get_db] = _inner


def _clear_db():
    app.dependency_overrides.pop(get_db, None)


def _no_redis():
    """Redis チェックをバイパス（フェイルオープン）"""
    return patch("core.token_store._get_redis", side_effect=Exception("no redis"))


# ────────────────────────────────────────────────
# GET /api/v1/users — Developer 以上のみ
# ────────────────────────────────────────────────

class TestListUsersRBAC:
    """ユーザ一覧: Developer/Approver/SecurityAdmin/GlobalAdmin → 200、Viewer → 403"""

    def test_viewer_gets_403(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["Viewer"]))
                assert resp.status_code == 403
        finally:
            _clear_db()

    def test_no_role_gets_403(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token([]))
                assert resp.status_code == 403
        finally:
            _clear_db()

    def test_developer_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["Developer"]))
                assert resp.status_code == 200
        finally:
            _clear_db()

    def test_approver_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["Approver"]))
                assert resp.status_code == 200
        finally:
            _clear_db()

    def test_security_admin_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["SecurityAdmin"]))
                assert resp.status_code == 200
        finally:
            _clear_db()

    def test_global_admin_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["GlobalAdmin"]))
                assert resp.status_code == 200
        finally:
            _clear_db()


# ────────────────────────────────────────────────
# GET /api/v1/audit-logs — SecurityAdmin/GlobalAdmin のみ
# ────────────────────────────────────────────────

class TestAuditLogsRBAC:
    """監査ログ検索: SecurityAdmin/GlobalAdmin → 200、Developer → 403"""

    def test_developer_gets_403(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["Developer"]))
                assert resp.status_code == 403
        finally:
            _clear_db()

    def test_approver_gets_403(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["Approver"]))
                assert resp.status_code == 403
        finally:
            _clear_db()

    def test_viewer_gets_403(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["Viewer"]))
                assert resp.status_code == 403
        finally:
            _clear_db()

    def test_security_admin_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["SecurityAdmin"]))
                assert resp.status_code == 200
        finally:
            _clear_db()

    def test_global_admin_gets_200(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["GlobalAdmin"]))
                assert resp.status_code == 200
        finally:
            _clear_db()


# ────────────────────────────────────────────────
# 403 レスポンス形式の検証
# ────────────────────────────────────────────────

class TestForbiddenResponseFormat:
    """403 Forbidden レスポンスに適切なメッセージが含まれること"""

    def test_403_contains_role_hint(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/users", headers=_token(["Viewer"]))
                assert resp.status_code == 403
                body = resp.json()
                assert "detail" in body
                assert "Developer" in body["detail"] or "ロール" in body["detail"]
        finally:
            _clear_db()

    def test_audit_403_contains_security_admin_hint(self) -> None:
        _mock_db()
        try:
            with _no_redis():
                resp = client.get("/api/v1/audit-logs", headers=_token(["Developer"]))
                assert resp.status_code == 403
                body = resp.json()
                assert "SecurityAdmin" in body["detail"] or "ロール" in body["detail"]
        finally:
            _clear_db()
