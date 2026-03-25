"""
JWT 認証ユニットテスト

security.py と auth.py の動作を検証
準拠: ISO27001 A.8.2 / NIST CSF PR.AA-02
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.auth import CurrentUser, get_current_user
from core.database import get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_subject_from_token,
    hash_password,
    verify_password,
)
from main import app

client = TestClient(app, base_url="http://localhost")


# ============================================================
# パスワードハッシュテスト
# ============================================================
class TestPasswordHashing:
    """bcrypt パスワードハッシュの動作検証"""

    def test_hash_is_different_from_plain(self) -> None:
        """ハッシュはプレーンテキストと異なる"""
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_verify_correct_password(self) -> None:
        """正しいパスワードは検証成功"""
        hashed = hash_password("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_verify_wrong_password(self) -> None:
        """誤ったパスワードは検証失敗"""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_same_password_produces_different_hashes(self) -> None:
        """bcrypt はランダムなソルトで毎回異なるハッシュを生成する"""
        h1 = hash_password("same-pass")
        h2 = hash_password("same-pass")
        assert h1 != h2


# ============================================================
# JWT トークン生成・検証テスト
# ============================================================
class TestJWTTokens:
    """JWT アクセストークンとリフレッシュトークンの生成・検証"""

    def test_access_token_contains_subject(self) -> None:
        """アクセストークンに subject が含まれる"""
        token = create_access_token("user-001")
        payload = decode_token(token)
        assert payload["sub"] == "user-001"

    def test_access_token_type_claim(self) -> None:
        """アクセストークンの type クレームが 'access'"""
        token = create_access_token("user-001")
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_access_token_with_extra_claims(self) -> None:
        """追加クレームがトークンに含まれる"""
        token = create_access_token(
            "user-001",
            extra_claims={"roles": ["GlobalAdmin"], "email": "admin@example.com"},
        )
        payload = decode_token(token)
        assert payload["roles"] == ["GlobalAdmin"]
        assert payload["email"] == "admin@example.com"

    def test_expired_token_raises_error(self) -> None:
        """期限切れトークンは JWTError を発生させる"""
        from jose import JWTError

        token = create_access_token("user-001", expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_token(token)

    def test_refresh_token_type_claim(self) -> None:
        """リフレッシュトークンの type クレームが 'refresh'"""
        token = create_refresh_token("user-001")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_get_subject_returns_user_id(self) -> None:
        """get_subject_from_token は有効なトークンから user_id を返す"""
        token = create_access_token("user-abc")
        assert get_subject_from_token(token) == "user-abc"

    def test_get_subject_returns_none_on_invalid_token(self) -> None:
        """get_subject_from_token は不正なトークンで None を返す"""
        assert get_subject_from_token("invalid.token.here") is None

    def test_tampered_token_fails_verification(self) -> None:
        """改ざんされたトークンは検証失敗"""
        from jose import JWTError

        token = create_access_token("user-001")
        # 署名部分を改ざん
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsignature"
        with pytest.raises(JWTError):
            decode_token(tampered)


# ============================================================
# FastAPI Dependency テスト（get_current_user）
# ============================================================
class TestGetCurrentUserDependency:
    """get_current_user Dependency の動作検証"""

    @pytest.fixture
    def valid_token(self) -> str:
        return create_access_token("user-001", extra_claims={"roles": ["Developer"]})

    @pytest.mark.asyncio
    async def test_valid_token_returns_current_user(self, valid_token: str) -> None:
        """有効なトークンで CurrentUser が返る"""
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
        user = await get_current_user(creds)
        assert isinstance(user, CurrentUser)
        assert user.user_id == "user-001"

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self) -> None:
        """認証情報なしは 401 を返す"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self) -> None:
        """期限切れトークンは 401 を返す"""
        from fastapi.security import HTTPAuthorizationCredentials

        expired = create_access_token("user-001", expires_delta=timedelta(seconds=-1))
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(creds)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_access(self) -> None:
        """リフレッシュトークンをアクセストークンとして使うと 401"""
        from fastapi.security import HTTPAuthorizationCredentials

        refresh = create_refresh_token("user-001")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=refresh)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(creds)
        assert exc_info.value.status_code == 401


# ============================================================
# CurrentUser ヘルパーテスト
# ============================================================
class TestCurrentUser:
    """CurrentUser 値オブジェクトのロール判定"""

    def test_has_role_returns_true(self) -> None:
        user = CurrentUser(user_id="u1", roles=["GlobalAdmin", "Developer"])
        assert user.has_role("GlobalAdmin") is True

    def test_has_role_returns_false(self) -> None:
        user = CurrentUser(user_id="u1", roles=["Developer"])
        assert user.has_role("GlobalAdmin") is False

    def test_has_role_empty_roles(self) -> None:
        user = CurrentUser(user_id="u1", roles=[])
        assert user.has_role("ReadOnly") is False


# ============================================================
# ヘルスエンドポイントの認証不要確認（公開エンドポイント）
# ============================================================
class TestPublicEndpoints:
    """認証不要の公開エンドポイントが引き続き動作する"""

    def test_health_endpoint_no_auth_required(self) -> None:
        """ヘルスチェックは認証なしでアクセス可能"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ============================================================
# テスト環境専用ログインエンドポイント
# ============================================================
class TestLoginEndpoint:
    """POST /api/v1/auth/login テスト環境専用ログインの動作検証"""

    def setup_method(self) -> None:
        """DB 依存性をモックに差し替える（ローカル PostgreSQL 不要）"""
        mock_user_id = uuid.uuid4()

        async def _db():
            mock = AsyncMock()
            result = MagicMock()
            # ユーザーが存在しない → 新規作成フローを通す
            result.scalar_one_or_none.return_value = None
            mock.execute.return_value = result
            mock.commit = AsyncMock()
            mock.add = MagicMock()

            # refresh は user.id をそのまま維持（コンストラクタで設定済み）
            async def _refresh(obj):
                if not hasattr(obj, '_id_set'):
                    obj.id = mock_user_id

            mock.refresh.side_effect = _refresh
            yield mock

        app.dependency_overrides[get_db] = _db

    def teardown_method(self) -> None:
        """DB モックをクリア"""
        app.dependency_overrides.pop(get_db, None)

    def test_login_success_returns_tokens(self) -> None:
        """正常ログインはアクセストークンとリフレッシュトークンを返す"""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self) -> None:
        """誤ったパスワードは 401 を返す"""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "WRONG_PASSWORD"},
        )
        assert resp.status_code == 401

    def test_login_wrong_username_returns_401(self) -> None:
        """存在しないユーザー名は 401 を返す"""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "notexist", "password": "AdminPass123!"},
        )
        assert resp.status_code == 401

    def test_login_access_token_is_valid_jwt(self) -> None:
        """返却されたアクセストークンが有効な JWT であることを確認"""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPass123!"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert "sub" in payload
        assert payload.get("type") == "access"
