"""
JWT セキュリティユーティリティ
アクセストークン・リフレッシュトークンの生成と検証

RS256（非対称鍵）優先。JWT_PRIVATE_KEY / JWT_PUBLIC_KEY 未設定時は
HS256 + JWT_SECRET_KEY にフォールバック（開発・テスト環境向け）。

全トークンに jti（JWT ID）クレームを付与し、Redis ブラックリストによる
ピンポイント無効化（ログアウト・強制失効）を可能にする。

準拠:
- ISO27001:2022 A.8.2 情報アクセス制限 / A.5.15 アクセス制御
- NIST CSF 2.0 PR.AA-02 認証情報管理
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

# --- パスワードハッシュコンテキスト（bcrypt）---
# OWASP Password Storage Cheat Sheet 2024: rounds >= 12 推奨
# ISO27001 A.8.1: 認証情報の強度基準
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=13,
)


def _signing_key() -> str:
    """JWT 署名キー（RS256 優先、未設定時は HS256 フォールバック）"""
    if settings.JWT_ALGORITHM == "RS256" and settings.JWT_PRIVATE_KEY:
        return settings.JWT_PRIVATE_KEY.replace("\\n", "\n")
    return settings.JWT_SECRET_KEY


def _verify_key() -> str:
    """JWT 検証キー（RS256 優先、未設定時は HS256 フォールバック）"""
    if settings.JWT_ALGORITHM == "RS256" and settings.JWT_PUBLIC_KEY:
        return settings.JWT_PUBLIC_KEY.replace("\\n", "\n")
    return settings.JWT_SECRET_KEY


def _effective_algorithm() -> str:
    """実効アルゴリズム（RS256 鍵が揃っている場合のみ RS256）"""
    if settings.JWT_ALGORITHM == "RS256" and settings.JWT_PRIVATE_KEY and settings.JWT_PUBLIC_KEY:
        return "RS256"
    return "HS256"


def hash_password(plain: str) -> str:
    """プレーンテキストパスワードを bcrypt でハッシュ化"""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """パスワードを検証する"""
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """JWT アクセストークンを生成する

    Args:
        subject: トークンの主体（通常はユーザーID）
        extra_claims: 追加クレーム（roles, email 等）
        expires_delta: カスタム有効期限（省略時は設定値を使用）

    Returns:
        署名済み JWT 文字列（jti クレーム付き）
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),  # JWT ID — Redis ブラックリストによる個別無効化に使用
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, _signing_key(), algorithm=_effective_algorithm())


def create_refresh_token(subject: str) -> str:
    """JWT リフレッシュトークンを生成する（jti クレーム付き）"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),  # 個別無効化用 JWT ID
        "type": "refresh",
    }
    return jwt.encode(payload, _signing_key(), algorithm=_effective_algorithm())


def decode_token(token: str) -> dict[str, Any]:
    """JWT トークンをデコード・検証する

    Args:
        token: JWT 文字列

    Returns:
        デコードされたペイロード辞書

    Raises:
        JWTError: トークンが無効・期限切れの場合
    """
    return jwt.decode(token, _verify_key(), algorithms=[_effective_algorithm()])


def get_subject_from_token(token: str) -> str | None:
    """トークンから subject (ユーザーID) を安全に取得する

    検証失敗時は None を返す（例外を握り潰さない用途では decode_token を使用すること）
    """
    try:
        payload = decode_token(token)
        return str(payload.get("sub"))
    except JWTError:
        return None
