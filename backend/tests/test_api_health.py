"""
API ヘルスチェック & 設定のユニットテスト
FastAPI TestClient を使用してエンドポイントを検証
"""

from fastapi.testclient import TestClient

from main import app
from core.config import settings


client = TestClient(app, base_url="http://localhost")


class TestHealthEndpoints:
    """ヘルスチェックエンドポイントのテスト"""

    def test_root_health(self) -> None:
        """GET /health → 200 OK"""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "env" in body

    def test_api_v1_health(self) -> None:
        """GET /api/v1/health → 200 OK"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    def test_health_version_matches_settings(self) -> None:
        """ヘルスチェックのバージョンが設定値と一致する"""
        resp = client.get("/health")
        assert resp.json()["version"] == settings.APP_VERSION

    def test_unknown_endpoint_returns_404(self) -> None:
        """存在しないエンドポイント → 404"""
        resp = client.get("/api/v1/nonexistent-endpoint-xyz")
        assert resp.status_code == 404


class TestSettings:
    """設定クラスのユニットテスト"""

    def test_default_app_version(self) -> None:
        """デフォルト APP_VERSION は 1.0.0"""
        assert settings.APP_VERSION == "1.0.0"

    def test_jwt_algorithm(self) -> None:
        """JWT アルゴリズムが HS256"""
        assert settings.JWT_ALGORITHM == "HS256"

    def test_jwt_access_token_expire_positive(self) -> None:
        """JWT アクセストークン有効期限は正の整数"""
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_allowed_hosts_is_list(self) -> None:
        """ALLOWED_HOSTS はリスト型"""
        assert isinstance(settings.ALLOWED_HOSTS, list)
        assert len(settings.ALLOWED_HOSTS) > 0

    def test_allowed_origins_is_list(self) -> None:
        """ALLOWED_ORIGINS はリスト型"""
        assert isinstance(settings.ALLOWED_ORIGINS, list)

    def test_app_env_valid_value(self) -> None:
        """APP_ENV は定義済みの値"""
        assert settings.APP_ENV in ("development", "test", "production")
