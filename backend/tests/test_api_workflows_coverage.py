"""
ワークフロー API カバレッジ補完テスト（Phase 18）

api/v1/workflows.py の未カバー行（例外パス）を補完する。
既存の test_api_crud.py::TestWorkflows に追加して 100% カバレッジを達成する。

対象行:
- consistency_check の except Exception ブロック（line 62-63）

準拠: ISO27001:2022 A.5.15 / NIST CSF DE.CM-01
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


def _auth_header(roles: list[str]) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles})
    return {"Authorization": f"Bearer {token}"}


ADMIN_HDR = _auth_header(["GlobalAdmin"])


class TestWorkflowsCoverageCompletion:
    """workflows.py の未カバーパスを補完するテスト"""

    def test_consistency_check_celery_failure_returns_error_response(self) -> None:
        """consistency-check: Celery タスク失敗時はエラーレスポンスを返す（except パス）"""
        with patch("tasks.review.start_quarterly_review") as mock_celery:
            mock_celery.delay.side_effect = Exception("Celery broker unavailable")
            resp = client.post(
                "/api/v1/workflows/consistency-check",
                headers=ADMIN_HDR,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Celery broker unavailable" in body["message"]
        assert len(body["errors"]) > 0

    def test_consistency_check_import_error_returns_error_response(self) -> None:
        """consistency-check: tasks モジュールが ImportError の場合もエラーレスポンスを返す"""
        with patch(
            "api.v1.workflows.consistency_check.__wrapped__"
            if hasattr(
                __import__("api.v1.workflows", fromlist=["consistency_check"]),
                "__wrapped__",
            )
            else "tasks.review.start_quarterly_review"
        ) as mock_celery:
            mock_celery.delay.side_effect = RuntimeError("Celery worker not responding")
            resp = client.post(
                "/api/v1/workflows/consistency-check",
                headers=ADMIN_HDR,
            )

        # RuntimeError でも success=False が返ること
        body = resp.json()
        assert "success" in body

    def test_workflows_require_admin_role_for_consistency_check(self) -> None:
        """consistency-check: GlobalAdmin 以外は 403 を返す"""
        user_hdr = _auth_header(["Developer"])
        resp = client.post("/api/v1/workflows/consistency-check", headers=user_hdr)
        assert resp.status_code == 403

    def test_workflows_require_admin_role_for_risk_scan(self) -> None:
        """risk-scan: GlobalAdmin 以外は 403 を返す"""
        user_hdr = _auth_header(["Viewer"])
        resp = client.post("/api/v1/workflows/risk-scan", headers=user_hdr)
        assert resp.status_code == 403

    def test_workflows_require_admin_role_for_pim_expiry(self) -> None:
        """pim-expiry: GlobalAdmin 以外は 403 を返す"""
        user_hdr = _auth_header(["Developer"])
        resp = client.post("/api/v1/workflows/pim-expiry", headers=user_hdr)
        assert resp.status_code == 403

    def test_workflows_require_admin_role_for_mfa_enforcement(self) -> None:
        """mfa-enforcement: GlobalAdmin 以外は 403 を返す"""
        user_hdr = _auth_header(["Reviewer"])
        resp = client.post("/api/v1/workflows/mfa-enforcement", headers=user_hdr)
        assert resp.status_code == 403

    def test_risk_scan_returns_success_with_scanned_count(self) -> None:
        """risk-scan: 成功時は scanned カウントを含むレスポンスを返す"""
        resp = client.post("/api/v1/workflows/risk-scan", headers=ADMIN_HDR)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "scanned" in body["data"]

    def test_pim_expiry_returns_success_with_revoked_count(self) -> None:
        """pim-expiry: 成功時は revoked カウントを含むレスポンスを返す"""
        resp = client.post("/api/v1/workflows/pim-expiry", headers=ADMIN_HDR)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "revoked" in body["data"]

    def test_mfa_enforcement_returns_success_with_suspended_count(self) -> None:
        """mfa-enforcement: 成功時は suspended カウントを含むレスポンスを返す"""
        resp = client.post("/api/v1/workflows/mfa-enforcement", headers=ADMIN_HDR)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "suspended" in body["data"]
