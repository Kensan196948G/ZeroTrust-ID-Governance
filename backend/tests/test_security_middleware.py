"""
セキュリティヘッダー・レート制限ミドルウェアのテスト

SecurityHeadersMiddleware が:
- 全レスポンスに必須セキュリティヘッダーを付与すること
- API パスに Cache-Control: no-store を付与すること

RateLimitMiddleware が:
- 制限内リクエストを通過させること
- 制限超過時に 429 を返すこと
- インメモリフォールバックが機能すること
- API パス以外はスキップすること

を検証する。

準拠: ISO27001 A.8.22 / A.8.3 / NIST CSF PR.PT-3 / PR.AC-7
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token
from main import app

client = TestClient(app, base_url="http://localhost")


def _auth_header(roles: list[str] | None = None) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles or ["Developer"]})
    return {"Authorization": f"Bearer {token}"}


def _mock_db_override():
    from unittest.mock import AsyncMock

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


def _clear_db_override():
    app.dependency_overrides.pop(get_db, None)


# ────────────────────────────────────────────────
# HTTP セキュリティヘッダー検証
# ────────────────────────────────────────────────

class TestSecurityHeadersMiddleware:
    """全レスポンスにセキュリティヘッダーが付与されること"""

    def test_x_frame_options_is_deny(self) -> None:
        """/health レスポンスに X-Frame-Options: DENY が含まれる"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options_nosniff(self) -> None:
        """/health レスポンスに X-Content-Type-Options: nosniff が含まれる"""
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_xss_protection_header(self) -> None:
        """/health レスポンスに X-XSS-Protection ヘッダーが含まれる"""
        resp = client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    def test_strict_transport_security_header(self) -> None:
        """/health レスポンスに Strict-Transport-Security ヘッダーが含まれる"""
        resp = client.get("/health")
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_referrer_policy_header(self) -> None:
        """/health レスポンスに Referrer-Policy ヘッダーが含まれる"""
        resp = client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_content_security_policy_header(self) -> None:
        """/health レスポンスに Content-Security-Policy ヘッダーが含まれる"""
        resp = client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'none'" in csp

    def test_api_response_has_cache_control_no_store(self) -> None:
        """/api/ パスのレスポンスに Cache-Control: no-store が含まれる"""
        resp = client.get("/api/v1/health")
        assert resp.headers.get("cache-control") == "no-store"
        assert resp.headers.get("pragma") == "no-cache"

    def test_non_api_path_no_cache_control(self) -> None:
        """/health は Cache-Control: no-store を付与しない"""
        resp = client.get("/health")
        # /health は /api/ プレフィックスなし → Cache-Control は付与されない
        assert resp.headers.get("cache-control") != "no-store"

    def test_security_headers_on_authenticated_endpoint(self) -> None:
        """認証済みエンドポイントでもセキュリティヘッダーが付与される"""
        _mock_db_override()
        try:
            with patch("core.token_store._get_redis") as mock_redis:
                r = MagicMock()
                r.exists = MagicMock(return_value=0)
                mock_redis.return_value = r
                resp = client.get("/api/v1/users", headers=_auth_header())
                assert resp.status_code == 200
                assert resp.headers.get("x-frame-options") == "DENY"
                assert resp.headers.get("x-content-type-options") == "nosniff"
        finally:
            _clear_db_override()


# ────────────────────────────────────────────────
# レート制限検証
# ────────────────────────────────────────────────

class TestRateLimitMiddleware:
    """レート制限ミドルウェアの動作検証"""

    def test_normal_request_passes_with_ratelimit_header(self) -> None:
        """通常リクエストはレート制限内で通過し X-RateLimit-Limit ヘッダーを返す"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers

    def test_non_api_path_has_no_ratelimit_header(self) -> None:
        """/docs など非 API パスはレート制限をスキップする"""
        resp = client.get("/docs")
        # /docs はレート制限対象外なのでヘッダーなし
        assert "x-ratelimit-limit" not in resp.headers

    def test_rate_limit_exceeded_returns_429(self) -> None:
        """制限超過時に 429 Too Many Requests が返る（メモリカウンタモック使用）"""
        # Redis フォールバックをテスト: Redis を失敗させてメモリカウンタを使用
        # メモリカウンタの count を制限超過にパッチ
        with patch("core.rate_limit_middleware._check_rate_limit_redis", return_value=None):
            with patch("core.rate_limit_middleware._check_rate_limit_memory", return_value=False):
                resp = client.get("/api/v1/health")
                assert resp.status_code == 429
                data = resp.json()
                assert data["success"] is False
                assert "Too many requests" in data["errors"][0]["message"]

    def test_rate_limit_429_has_retry_after_header(self) -> None:
        """429 レスポンスに Retry-After ヘッダーが含まれる"""
        with patch("core.rate_limit_middleware._check_rate_limit_redis", return_value=None):
            with patch("core.rate_limit_middleware._check_rate_limit_memory", return_value=False):
                resp = client.get("/api/v1/health")
                assert resp.status_code == 429
                assert "retry-after" in resp.headers

    def test_redis_failure_falls_back_to_memory(self) -> None:
        """Redis 接続失敗時にインメモリカウンタにフォールバックして通過する"""
        with patch("core.rate_limit_middleware._check_rate_limit_redis", return_value=None):
            with patch("core.rate_limit_middleware._check_rate_limit_memory", return_value=True):
                resp = client.get("/api/v1/health")
                assert resp.status_code == 200

    def test_get_rate_limit_auth_path(self) -> None:
        """認証パスに対して厳しいレート制限値が設定されている"""
        from core.rate_limit_middleware import _get_rate_limit

        max_req, window = _get_rate_limit("/api/v1/auth/login")
        assert max_req <= 10  # 認証エンドポイントは最大 10 req/min
        assert window == 60

    def test_get_rate_limit_general_api(self) -> None:
        """一般 API パスに対してデフォルトのレート制限値が設定されている"""
        from core.rate_limit_middleware import _get_rate_limit

        max_req, window = _get_rate_limit("/api/v1/users")
        assert max_req >= 100  # 一般 API は 100+ req/min


# ────────────────────────────────────────────────
# ADConnector 未カバー行補完
# ────────────────────────────────────────────────

class TestADConnectorAdditional:
    """ADConnector の __init__ / __del__ / disable_account ログパスを検証"""

    def test_init_creates_ldap_connection(self) -> None:
        """__init__ が ldap3.Connection を作成する（lines 25-33）"""
        with patch("connectors.ad_connector.ldap3") as mock_ldap3:
            mock_server = MagicMock()
            mock_conn = MagicMock()
            mock_ldap3.Server.return_value = mock_server
            mock_ldap3.Connection.return_value = mock_conn
            mock_ldap3.ALL = "ALL"
            mock_ldap3.NTLM = "NTLM"

            from connectors.ad_connector import ADConnector
            connector = ADConnector()

            mock_ldap3.Server.assert_called_once()
            mock_ldap3.Connection.assert_called_once()
            assert connector.conn is mock_conn

    def test_disable_account_logging_on_success(self) -> None:
        """disable_account が成功時にログを出力する（line 95）"""
        with patch("connectors.ad_connector.ldap3") as mock_ldap3:
            mock_conn = MagicMock()
            mock_conn.modify.return_value = True
            mock_ldap3.Server.return_value = MagicMock()
            mock_ldap3.Connection.return_value = mock_conn
            mock_ldap3.ALL = "ALL"
            mock_ldap3.NTLM = "NTLM"
            mock_ldap3.MODIFY_REPLACE = "MODIFY_REPLACE"

            from connectors.ad_connector import ADConnector
            connector = ADConnector()
            result = connector.disable_account("CN=yamada,OU=Users,DC=mirai,DC=local")
            assert result is True

    def test_del_calls_unbind(self) -> None:
        """__del__ が conn.unbind() を呼び出す（lines 113-114）"""
        with patch("connectors.ad_connector.ldap3") as mock_ldap3:
            mock_conn = MagicMock()
            mock_ldap3.Server.return_value = MagicMock()
            mock_ldap3.Connection.return_value = mock_conn
            mock_ldap3.ALL = "ALL"
            mock_ldap3.NTLM = "NTLM"

            from connectors.ad_connector import ADConnector
            connector = ADConnector()
            connector.__del__()
            mock_conn.unbind.assert_called_once()

    def test_del_swallows_exception(self) -> None:
        """__del__ が unbind 例外を握り潰す（耐障害設計）"""
        with patch("connectors.ad_connector.ldap3") as mock_ldap3:
            mock_conn = MagicMock()
            mock_conn.unbind.side_effect = Exception("connection already closed")
            mock_ldap3.Server.return_value = MagicMock()
            mock_ldap3.Connection.return_value = mock_conn
            mock_ldap3.ALL = "ALL"
            mock_ldap3.NTLM = "NTLM"

            from connectors.ad_connector import ADConnector
            connector = ADConnector()
            connector.__del__()  # 例外が発生しないこと


# ────────────────────────────────────────────────
# HengeOneConnector 未カバー行補完
# ────────────────────────────────────────────────


class TestHengeOneConnectorAdditional:
    """HengeOneConnector の account_active 例外パスを検証"""

    @pytest.fixture
    def connector(self):
        from connectors.hengeone_connector import HengeOneConnector
        return HengeOneConnector.__new__(HengeOneConnector)

    @pytest.mark.asyncio
    async def test_account_active_no_resources_returns_false(self, connector) -> None:
        """account_active が totalResults=1 かつ Resources なし → False を返す（line 120）"""
        from unittest.mock import AsyncMock as _AsyncMock

        mock_response = MagicMock()
        # totalResults=0 → line 120 の `return False` を通る
        mock_response.json.return_value = {"totalResults": 0}

        mock_client = _AsyncMock()
        mock_client.__aenter__ = _AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = _AsyncMock(return_value=False)
        mock_client.get = _AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("inactive.user")
        assert result is False

    @pytest.mark.asyncio
    async def test_account_active_exception_returns_false(self, connector) -> None:
        """account_active が例外時に False を返す（lines 121-122）"""
        from unittest.mock import AsyncMock as _AsyncMock

        mock_client = _AsyncMock()
        mock_client.__aenter__ = _AsyncMock(side_effect=Exception("timeout"))

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("error.user")
        assert result is False
