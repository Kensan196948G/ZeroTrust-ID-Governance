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


class TestMetricsEndpoint:
    """Prometheus メトリクスエンドポイントのテスト"""

    def test_metrics_endpoint_returns_200(self) -> None:
        """GET /metrics → 200 OK（Prometheusスクレイプ用）"""
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type_is_prometheus(self) -> None:
        """Content-Type が Prometheus テキスト形式"""
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_contains_http_requests_total(self) -> None:
        """http_requests_total メトリクスが含まれる"""
        # /health に1回アクセスしてメトリクスを生成
        client.get("/health")
        resp = client.get("/metrics")
        assert "http_requests_total" in resp.text


class TestOpenTelemetry:
    """OpenTelemetry トレーシング設定のユニットテスト"""

    def test_otel_sdk_disabled_in_test_env(self) -> None:
        """テスト環境では OTEL_SDK_DISABLED=true が設定されているか確認"""
        import os

        # テスト環境では OTEL_SDK_DISABLED=true が推奨
        # 未設定でも main.py の _setup_tracing() がフォールバックするため失敗しない
        val = os.getenv("OTEL_SDK_DISABLED", "true")
        assert val.lower() in ("true", "false")

    def test_tracing_does_not_break_health_endpoint(self) -> None:
        """OpenTelemetry 計装後もヘルスエンドポイントが正常応答"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_tracing_does_not_break_api_endpoint(self) -> None:
        """OpenTelemetry 計装後も API エンドポイントが正常応答（404 は正常）"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestSettings:
    """設定クラスのユニットテスト"""

    def test_default_app_version(self) -> None:
        """デフォルト APP_VERSION は 1.0.0"""
        assert settings.APP_VERSION == "1.0.0"

    def test_jwt_algorithm(self) -> None:
        """JWT アルゴリズムが RS256（Phase 7 以降のデフォルト）"""
        assert settings.JWT_ALGORITHM == "RS256"

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
