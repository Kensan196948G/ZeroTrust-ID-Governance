"""
監査ログ自動記録ミドルウェアのテスト

AuditLoggingMiddleware が:
- API リクエストを AuditLog レコードとして記録しようとすること
- DB エラー時もレスポンスに影響しないこと
- ヘルスチェック・非 API パスは記録しないこと
を検証する。

準拠: ISO27001 A.8.15 ログ記録 / NIST CSF DE.CM-01
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


def _auth_header(roles: list[str] | None = None) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles or ["Developer"]})
    return {"Authorization": f"Bearer {token}"}


def _mock_db_override():
    """空結果を返す DB モック"""
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


class TestAuditMiddlewareSkipPaths:
    """スキップパスはログ記録されないことを検証"""

    def test_health_check_returns_200(self) -> None:
        """/health はミドルウェアをスキップして正常応答"""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_api_health_check_returns_200(self) -> None:
        """/api/v1/health はスキップ対象"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestAuditMiddlewareDbFailureSafety:
    """DB 書き込み失敗時もレスポンスに影響しないことを検証"""

    def test_api_request_succeeds_even_if_audit_write_fails(self) -> None:
        """監査ログ DB 書き込みエラー時も 200 が返る"""
        _mock_db_override()
        try:
            with patch(
                "core.audit_middleware.AsyncSessionLocal",
                side_effect=Exception("DB connection failed"),
            ):
                resp = client.get("/api/v1/users", headers=_auth_header())
                assert resp.status_code == 200
        finally:
            _clear_db_override()

    def test_unauthenticated_request_returns_401_not_500(self) -> None:
        """認証なし → ミドルウェアが例外を握り潰しても 401 が返る"""
        resp = client.get("/api/v1/users")
        assert resp.status_code == 401


class TestAuditMiddlewareMetadataExtraction:
    """ミドルウェアがリクエスト情報を正しく抽出することを検証"""

    def test_audit_log_written_with_correct_fields(self) -> None:
        """認証済みリクエスト → AuditLog に正しいフィールドで add が呼ばれる"""
        _mock_db_override()
        captured_logs: list = []

        # async with AsyncSessionLocal() as session: を正しくモック
        mock_session = AsyncMock()
        mock_session.add = lambda obj: captured_logs.append(obj)
        mock_session.commit = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_cm)

        try:
            with patch("core.audit_middleware.AsyncSessionLocal", mock_factory):
                resp = client.get("/api/v1/users", headers=_auth_header())
                assert resp.status_code == 200

            # AuditLog オブジェクトが追加されたことを確認
            assert len(captured_logs) == 1
            log = captured_logs[0]
            assert log.event_type == "api_read"
            assert "GET /api/v1/users" in log.action
            assert log.result == "success"
        finally:
            _clear_db_override()

    def test_failed_request_recorded_as_failure(self) -> None:
        """401 エラーは result='failure' で記録される"""
        captured_logs: list = []

        mock_session = AsyncMock()
        mock_session.add = lambda obj: captured_logs.append(obj)
        mock_session.commit = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_cm)

        with patch("core.audit_middleware.AsyncSessionLocal", mock_factory):
            resp = client.get("/api/v1/users")  # 認証なし → 401
            assert resp.status_code == 401

        assert len(captured_logs) == 1
        assert captured_logs[0].result == "failure"


class TestAuditMiddlewareBoundaryConditions:
    """ミドルウェアの境界条件・例外パスを検証"""

    def test_jwt_error_in_extract_user_is_swallowed(self) -> None:
        """無効 JWT: _extract_user_from_request が JWTError を握り潰して処理続行（lines 57-59）"""
        # 不正な Bearer トークン → decode_token が JWTError を投げる
        # ミドルウェアはエラーを無視して user_id=None のままリクエストを継続する
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        # 認証は 401 を返すが、ミドルウェアがクラッシュしないことを確認
        assert resp.status_code == 401

    def test_x_forwarded_for_header_used_as_client_ip(self) -> None:
        """X-Forwarded-For ヘッダーが actor_ip として記録される（line 66）"""
        _mock_db_override()
        captured_logs: list = []

        mock_session = AsyncMock()
        mock_session.add = lambda obj: captured_logs.append(obj)
        mock_session.commit = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        try:
            with patch("core.audit_middleware.AsyncSessionLocal", MagicMock(return_value=mock_cm)):
                with patch("core.token_store._get_redis") as mock_redis:
                    r = MagicMock()
                    r.exists = MagicMock(return_value=0)
                    mock_redis.return_value = r
                    resp = client.get(
                        "/api/v1/users",
                        headers={
                            **_auth_header(),
                            "X-Forwarded-For": "203.0.113.42, 10.0.0.1",
                        },
                    )
                    assert resp.status_code == 200

            assert len(captured_logs) == 1
            assert captured_logs[0].actor_ip == "203.0.113.42"
        finally:
            _clear_db_override()

    def test_non_api_path_skips_audit_log(self) -> None:
        """/api/ 以外のパスは監査ログを記録せずリクエストを通す（line 91）"""
        captured_logs: list = []

        mock_session = AsyncMock()
        mock_session.add = lambda obj: captured_logs.append(obj)
        mock_session.commit = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("core.audit_middleware.AsyncSessionLocal", MagicMock(return_value=mock_cm)):
            # /api/ プレフィックスなし → ミドルウェアをスキップ
            client.get("/docs")

        # /docs は FastAPI デフォルトで存在するので 200 を返す
        # 重要: 監査ログ add() は呼ばれない
        assert len(captured_logs) == 0

    def test_invalid_uuid_in_jwt_sub_is_handled(self) -> None:
        """JWT sub が UUID でない場合 ValueError を握り潰して処理続行（lines 99-100）"""
        # sub が UUID 形式でないトークンを生成
        non_uuid_token = create_access_token(
            "not-a-valid-uuid",
            extra_claims={"roles": ["Developer"]},
        )

        _mock_db_override()
        captured_logs: list = []

        mock_session = AsyncMock()
        mock_session.add = lambda obj: captured_logs.append(obj)
        mock_session.commit = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        try:
            with patch("core.audit_middleware.AsyncSessionLocal", MagicMock(return_value=mock_cm)):
                with patch("core.token_store._get_redis") as mock_redis:
                    r = MagicMock()
                    r.exists = MagicMock(return_value=0)
                    mock_redis.return_value = r
                    resp = client.get(
                        "/api/v1/users",
                        headers={"Authorization": f"Bearer {non_uuid_token}"},
                    )
                    # ミドルウェアがクラッシュせず応答が返ること
                    assert resp.status_code in (200, 401)

            # actor_user_id は None になる（UUID 変換失敗）
            assert len(captured_logs) == 1
            assert captured_logs[0].actor_user_id is None
        finally:
            _clear_db_override()
