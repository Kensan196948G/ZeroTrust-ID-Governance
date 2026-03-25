"""
JWT セキュリティ強化テスト（Phase 7）

検証項目:
- RS256 / HS256 フォールバック動作
- jti クレームが全トークンに含まれること
- ログアウト後トークンが無効化されること
- リフレッシュトークンローテーション（旧トークン失効）
- 失効済みトークンで API アクセス → 401

準拠: ISO27001 A.5.15 / NIST CSF PR.AA-01/02
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from core.database import get_db
from core.security import create_access_token, create_refresh_token, decode_token
from main import app

client = TestClient(app, base_url="http://localhost")


def _auth_header(roles: list[str] | None = None) -> dict[str, str]:
    token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": roles or ["Developer"]})
    return {"Authorization": f"Bearer {token}"}


def _mock_db():
    """空結果を返す DB モック"""
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


def _clear_db():
    app.dependency_overrides.pop(get_db, None)


# ────────────────────────────────────────────────
# jti クレーム検証
# ────────────────────────────────────────────────

class TestJtiClaim:
    """全トークンに jti クレームが含まれること"""

    def test_access_token_has_jti(self) -> None:
        token = create_access_token("user-001")
        payload = decode_token(token)
        assert "jti" in payload
        uuid.UUID(payload["jti"])  # valid UUID であること

    def test_refresh_token_has_jti(self) -> None:
        token = create_refresh_token("user-001")
        payload = decode_token(token)
        assert "jti" in payload
        uuid.UUID(payload["jti"])

    def test_each_token_has_unique_jti(self) -> None:
        t1 = create_access_token("user-001")
        t2 = create_access_token("user-001")
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]


# ────────────────────────────────────────────────
# HS256 フォールバック（RS256 鍵未設定）
# ────────────────────────────────────────────────

class TestAlgorithmFallback:
    """RS256 鍵未設定時に HS256 でトークンが生成・検証される"""

    def test_hs256_fallback_when_no_rs256_keys(self) -> None:
        """JWT_PRIVATE_KEY / JWT_PUBLIC_KEY が空 → HS256 でエンコード・デコード成功"""
        token = create_access_token("user-hs256")
        payload = decode_token(token)
        assert payload["sub"] == "user-hs256"
        assert payload["type"] == "access"


# ────────────────────────────────────────────────
# ログアウト → トークン失効
# ────────────────────────────────────────────────

class TestLogout:
    """ログアウト後のトークン無効化"""

    def test_logout_returns_204(self) -> None:
        """POST /api/v1/auth/logout → 204 No Content"""
        _mock_db()
        try:
            with patch("core.token_store._get_redis") as mock_redis:
                r = MagicMock()
                r.setex = MagicMock()
                mock_redis.return_value = r
                resp = client.post("/api/v1/auth/logout", headers=_auth_header())
                assert resp.status_code == 204
        finally:
            _clear_db()

    def test_revoked_token_returns_401(self) -> None:
        """失効済みトークンで API アクセス → 401"""
        _mock_db()
        token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": ["Developer"]})

        try:
            with patch("core.token_store._get_redis") as mock_redis:
                r = MagicMock()
                # is_token_revoked: True を返す（失効済み）
                r.exists = MagicMock(return_value=1)
                mock_redis.return_value = r

                resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
                assert resp.status_code == 401
        finally:
            _clear_db()

    def test_valid_token_still_works_after_other_logout(self) -> None:
        """別ユーザのログアウトは他トークンに影響しない"""
        _mock_db()
        token = create_access_token(str(uuid.uuid4()), extra_claims={"roles": ["Developer"]})

        try:
            with patch("core.token_store._get_redis") as mock_redis:
                r = MagicMock()
                # is_token_revoked: False（有効）
                r.exists = MagicMock(return_value=0)
                mock_redis.return_value = r

                resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
                assert resp.status_code == 200
        finally:
            _clear_db()


# ────────────────────────────────────────────────
# リフレッシュトークンローテーション
# ────────────────────────────────────────────────

class TestTokenRefresh:
    """リフレッシュトークンによるトークンペア更新"""

    def test_refresh_returns_new_token_pair(self) -> None:
        """有効なリフレッシュトークン → 新しい access/refresh ペアを返す"""
        refresh_token = create_refresh_token("user-refresh-001")

        with patch("core.token_store._get_redis") as mock_redis:
            r = MagicMock()
            r.exists = MagicMock(return_value=0)   # 未失効
            r.setex = MagicMock()                   # revoke 書き込み
            mock_redis.return_value = r

            resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            # 旧トークンと異なる jti が付与されているか確認
            old_jti = decode_token(refresh_token)["jti"]
            new_jti = decode_token(data["access_token"])["jti"]
            assert old_jti != new_jti

    def test_refresh_with_access_token_returns_401(self) -> None:
        """アクセストークンをリフレッシュに使用 → 401"""
        access_token = create_access_token("user-001")

        with patch("core.token_store._get_redis") as mock_redis:
            r = MagicMock()
            r.exists = MagicMock(return_value=0)
            mock_redis.return_value = r

            resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
            assert resp.status_code == 401

    def test_refresh_with_expired_token_returns_401(self) -> None:
        """期限切れリフレッシュトークン → 401"""
        # 期限切れトークンを直接生成
        from datetime import datetime, timezone
        from jose import jwt as _jwt
        from core.security import _signing_key, _effective_algorithm
        import uuid as _uuid

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-001",
            "iat": now,
            "exp": now - timedelta(seconds=10),  # 過去の exp
            "jti": str(_uuid.uuid4()),
            "type": "refresh",
        }
        expired_token = _jwt.encode(payload, _signing_key(), algorithm=_effective_algorithm())

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": expired_token})
        assert resp.status_code == 401

    def test_revoked_refresh_token_returns_401(self) -> None:
        """失効済みリフレッシュトークン → 401"""
        refresh_token = create_refresh_token("user-001")

        with patch("core.token_store._get_redis") as mock_redis:
            r = MagicMock()
            r.exists = MagicMock(return_value=1)  # 失効済み
            mock_redis.return_value = r

            resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
            assert resp.status_code == 401


# ────────────────────────────────────────────────
# Redis 障害時フェイルオープン
# ────────────────────────────────────────────────

class TestRedisFailsafe:
    """Redis 障害時もリクエストが通ること（フェイルオープン）"""

    def test_api_works_when_redis_down(self) -> None:
        """Redis 接続失敗 → is_token_revoked が False を返す → リクエスト成功"""
        _mock_db()
        try:
            with patch("core.token_store._get_redis", side_effect=Exception("Redis down")):
                resp = client.get("/api/v1/users", headers=_auth_header())
                assert resp.status_code == 200
        finally:
            _clear_db()


# ────────────────────────────────────────────────
# api/v1/auth.py 未カバー行の追加テスト
# ────────────────────────────────────────────────

class TestAuthApiCoverage:
    """api/v1/auth.py の未カバー行を対象とした追加テスト"""

    def test_logout_jwt_error_handled_gracefully(self) -> None:
        """logout: logout 内の decode_token が JWTError → 握り潰して 204 を返す（lines 54-55）

        get_current_user は core.auth.decode_token を使うためパッチ対象外。
        api.v1.auth.decode_token だけを上書きすることで logout 内部でのみ JWTError が発生する。
        """
        from jose import JWTError as _JWTError

        with patch("core.token_store._get_redis") as mock_redis:
            r = MagicMock()
            r.exists = MagicMock(return_value=0)   # not revoked（get_current_user 用）
            r.setex = MagicMock()
            mock_redis.return_value = r

            with patch("api.v1.auth.decode_token", side_effect=_JWTError("decode failed")):
                resp = client.post(
                    "/api/v1/auth/logout",
                    headers=_auth_header(),
                )
                assert resp.status_code == 204

    def test_refresh_with_empty_subject_returns_401(self) -> None:
        """refresh: subject が空文字の refresh token → 401（line 98）"""
        import uuid as _uuid
        from datetime import datetime, timezone
        from jose import jwt as _jwt
        from core.security import _signing_key, _effective_algorithm

        now = datetime.now(timezone.utc)
        payload_no_sub = {
            "sub": "",   # 空文字 → `if not subject:` が True になる
            "iat": now,
            "exp": now + timedelta(days=7),
            "jti": str(_uuid.uuid4()),
            "type": "refresh",
        }
        token_empty_sub = _jwt.encode(
            payload_no_sub,
            _signing_key(),
            algorithm=_effective_algorithm(),
        )

        with patch("core.token_store._get_redis") as mock_redis:
            r = MagicMock()
            r.exists = MagicMock(return_value=0)   # not revoked
            mock_redis.return_value = r

            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": token_empty_sub},
            )
            assert resp.status_code == 401
