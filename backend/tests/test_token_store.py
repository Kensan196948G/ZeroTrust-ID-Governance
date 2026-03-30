"""
トークン失効ストア ユニットテスト

core/token_store.py の Redis ベース JWT ブラックリスト動作を検証する。

テスト戦略:
- Redis クライアントを unittest.mock でモック（実 Redis 不要）
- 正常系: revoke_token / is_token_revoked の基本動作
- 異常系: Redis 接続失敗時のフェイルオープン動作
- TTL 計算: exp タイムスタンプから残存秒数を正しく算出

準拠: ISO27001:2022 A.5.15 アクセス制御（強制失効制御）
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch



# ============================================================
# revoke_token テスト
# ============================================================
class TestRevokeToken:
    """revoke_token() — Redis への jti 登録動作を検証"""

    def test_revoke_token_calls_setex(self) -> None:
        """revoke_token は Redis の setex を正しいキーで呼び出す"""
        mock_redis = MagicMock()
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import revoke_token

            jti = "test-jti-001"
            exp = int(time.time()) + 3600  # 1時間後
            revoke_token(jti, exp)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        assert key == f"zt:revoked_token:{jti}"

    def test_revoke_token_ttl_is_positive(self) -> None:
        """TTL は正の値（残存秒数）が設定される"""
        mock_redis = MagicMock()
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import revoke_token

            exp = int(time.time()) + 3600
            revoke_token("jti-ttl-test", exp)

        ttl = mock_redis.setex.call_args[0][1]
        assert ttl > 0

    def test_revoke_token_ttl_minimum_is_one(self) -> None:
        """すでに期限切れの exp でも TTL は最低 1 秒"""
        mock_redis = MagicMock()
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import revoke_token

            exp = int(time.time()) - 100  # 過去の exp
            revoke_token("jti-expired", exp)

        ttl = mock_redis.setex.call_args[0][1]
        assert ttl >= 1

    def test_revoke_token_value_is_one(self) -> None:
        """Redis の値は '1' が格納される"""
        mock_redis = MagicMock()
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import revoke_token

            revoke_token("jti-value", int(time.time()) + 600)

        value = mock_redis.setex.call_args[0][2]
        assert value == "1"

    def test_revoke_token_redis_failure_does_not_raise(self) -> None:
        """Redis 接続失敗時は例外を raise しない（フォールトトレランス）"""
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Connection refused")
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import revoke_token

            # 例外が発生しないことを確認
            revoke_token("jti-fail", int(time.time()) + 600)

    def test_revoke_token_get_redis_failure_does_not_raise(self) -> None:
        """Redis クライアント取得失敗時も例外を raise しない"""
        with patch("core.token_store._get_redis", side_effect=Exception("Redis unavailable")):
            from core.token_store import revoke_token

            revoke_token("jti-no-redis", int(time.time()) + 600)


# ============================================================
# is_token_revoked テスト
# ============================================================
class TestIsTokenRevoked:
    """is_token_revoked() — ブラックリスト確認動作を検証"""

    def test_returns_true_when_key_exists(self) -> None:
        """Redis にキーが存在する場合は True（失効済み）"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import is_token_revoked

            result = is_token_revoked("revoked-jti")

        assert result is True

    def test_returns_false_when_key_not_exists(self) -> None:
        """Redis にキーが存在しない場合は False（有効）"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import is_token_revoked

            result = is_token_revoked("valid-jti")

        assert result is False

    def test_checks_correct_key_format(self) -> None:
        """正しいキープレフィックスでチェックされる"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import is_token_revoked

            is_token_revoked("target-jti")

        mock_redis.exists.assert_called_once_with("zt:revoked_token:target-jti")

    def test_fail_open_on_redis_error(self) -> None:
        """Redis 接続失敗時はフェイルオープン（False を返す）"""
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Connection timeout")
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import is_token_revoked

            result = is_token_revoked("jti-redis-error")

        assert result is False  # フェイルオープン: 可用性優先

    def test_fail_open_when_get_redis_fails(self) -> None:
        """Redis クライアント取得失敗時もフェイルオープン"""
        with patch("core.token_store._get_redis", side_effect=Exception("Redis down")):
            from core.token_store import is_token_revoked

            result = is_token_revoked("jti-no-connection")

        assert result is False  # フェイルオープン

    def test_returns_false_when_exists_returns_zero(self) -> None:
        """exists() が 0 以下の値を返した場合は False"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        with patch("core.token_store._get_redis", return_value=mock_redis):
            from core.token_store import is_token_revoked

            assert is_token_revoked("non-existent") is False
