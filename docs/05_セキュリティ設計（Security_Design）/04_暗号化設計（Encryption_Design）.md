# 暗号化設計（Encryption Design）

| 項目 | 内容 |
|------|------|
| 文書番号 | SEC-ENC-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新日 | 2026-03-24 |
| 作成者 | セキュリティ開発チーム |
| 承認者 | CISO |
| 分類 | 機密（Confidential） |
| 準拠規格 | ISO 27001 A.8.24 / NIST CSF PR.DS-1, PR.DS-2 / FIPS 140-2 / TLS 1.2以上 |

---

## 目次

1. [概要](#概要)
2. [通信暗号化（TLS）](#通信暗号化tls)
3. [JWT 署名（HS256 / RS256）](#jwt-署名hs256--rs256)
4. [データベース暗号化](#データベース暗号化)
5. [シークレット管理（Azure Key Vault）](#シークレット管理azure-key-vault)
6. [パスワードハッシュ（bcrypt）](#パスワードハッシュbcrypt)
7. [監査ログの改ざん防止](#監査ログの改ざん防止)

---

## 概要

本文書は、ZeroTrust-ID-Governance システムにおける暗号化の設計方針・実装仕様を定義する。保存データ（Data at Rest）と通信データ（Data in Transit）の両方に対して適切な暗号化を適用し、機密情報の機密性・完全性を保護する。

暗号化アルゴリズムは NIST 推奨アルゴリズムを採用し、量子耐性を考慮した将来の移行計画も視野に入れた設計とする。

### 暗号化適用範囲

| データ種別 | 暗号化区分 | 適用方式 |
|-----------|-----------|---------|
| API 通信 | Data in Transit | TLS 1.3（最低 TLS 1.2） |
| JWT トークン | 署名（完全性） | HS256 / RS256 |
| DB 全体 | Data at Rest | PostgreSQL TDE / Azure TDE |
| 個人情報（PII） | フィールドレベル | AES-256-GCM |
| パスワード | 一方向ハッシュ | bcrypt（cost=12） |
| シークレット | HSM 保護 | Azure Key Vault |
| 監査ログ | 改ざん防止 | SHA-256 ハッシュチェーン |
| バックアップ | Data at Rest | AES-256 |

---

## 通信暗号化（TLS）

### TLS 設定要件

```
最低バージョン: TLS 1.2
推奨バージョン: TLS 1.3

TLS 1.0 / 1.1: 完全無効化
SSL 3.0: 完全無効化
```

### 許可する暗号スイート

#### TLS 1.3（推奨）

```
TLS_AES_256_GCM_SHA384
TLS_CHACHA20_POLY1305_SHA256
TLS_AES_128_GCM_SHA256
```

#### TLS 1.2（後方互換）

```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256

# 以下は無効化（BEAST/POODLE 脆弱性対策）
TLS_RSA_WITH_AES_*       → 禁止（PFS なし）
TLS_*_CBC_*              → 禁止（CBC モード脆弱性）
TLS_*_RC4_*              → 禁止（RC4 廃止）
TLS_*_3DES_*             → 禁止（SWEET32 脆弱性）
```

### Nginx TLS 設定

```nginx
# /etc/nginx/conf.d/ssl.conf
server {
    listen 443 ssl http2;
    server_name id.example.com;

    # 証明書設定
    ssl_certificate     /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;
    ssl_dhparam         /etc/ssl/certs/dhparam4096.pem;  # 4096bit DH パラメータ

    # TLS バージョン制限
    ssl_protocols TLSv1.2 TLSv1.3;

    # 暗号スイート（TLS 1.3 は自動）
    ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-CHACHA20-POLY1305';
    ssl_prefer_server_ciphers on;

    # セッション設定
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;  # セッションチケット無効（PFS 確保）

    # HSTS（HTTP Strict Transport Security）
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # OCSP ステープリング（証明書失効確認の高速化）
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
}

# HTTP → HTTPS リダイレクト
server {
    listen 80;
    server_name id.example.com;
    return 301 https://$server_name$request_uri;
}
```

### HTTPS 強制設定

```python
# FastAPI HTTPS リダイレクトミドルウェア
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)

# または Azure Front Door / ALB でのオフロード設定
# X-Forwarded-Proto ヘッダーによる HTTPS 判定
```

### 証明書管理

| 項目 | 設定値 | 説明 |
|------|--------|------|
| 証明書種別 | EV SSL（Extended Validation） | 最高レベルの信頼性 |
| 鍵長 | RSA 4096bit または EC 384bit | NIST 推奨強度 |
| 有効期限 | 最大 398日（Let's Encrypt: 90日） | 業界標準 |
| 自動更新 | Certbot / Azure Certificate Manager | 期限切れ防止 |
| 失効確認 | OCSP ステープリング | リアルタイム失効チェック |
| CT ログ | Certificate Transparency 必須 | 不正証明書検知 |

---

## JWT 署名（HS256 / RS256）

### 署名アルゴリズムの使い分け

| アルゴリズム | 方式 | 用途 | 鍵管理 |
|------------|------|------|--------|
| **HS256** | HMAC-SHA256（対称鍵） | 内部サービス間トークン | 共有シークレット（Key Vault） |
| **RS256** | RSA-SHA256（非対称鍵） | 外部連携・Azure EntraID | 秘密鍵（Key Vault）+ 公開鍵（JWK Set） |
| **ES256** | ECDSA-SHA256（非対称鍵） | 将来の高性能環境 | EC 秘密鍵（Key Vault） |

### HS256 実装（内部トークン）

```python
import jwt
import os
from datetime import datetime, timedelta, timezone
from azure.keyvault.secrets import SecretClient

# Key Vault からシークレットを取得
def get_jwt_secret() -> str:
    """Azure Key Vault から JWT シークレットを取得"""
    client = SecretClient(
        vault_url=os.environ["KEY_VAULT_URL"],
        credential=DefaultAzureCredential()
    )
    secret = client.get_secret("jwt-secret-key")
    return secret.value

JWT_SECRET = get_jwt_secret()
JWT_ALGORITHM = "HS256"

def create_internal_token(payload: dict) -> str:
    """内部 API 用 JWT（HS256）を生成"""
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_internal_token(token: str) -> dict:
    """内部 JWT を検証・デコード"""
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "sub", "jti"]
            }
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException("トークンの有効期限が切れています")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenException(f"無効なトークンです: {str(e)}")
```

### RS256 実装（外部連携・Azure EntraID）

```python
import jwt
from jwt import PyJWKClient

# Azure EntraID の JWK Set URI
JWKS_URI = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

class EntraIDTokenVerifier:
    def __init__(self, tenant_id: str, client_id: str):
        self.jwks_client = PyJWKClient(
            JWKS_URI.format(tenant_id=tenant_id),
            cache_keys=True,        # 公開鍵をキャッシュ
            max_cached_keys=16      # キャッシュ最大数
        )
        self.tenant_id = tenant_id
        self.client_id = client_id

    def verify_id_token(self, id_token: str) -> dict:
        """
        Azure EntraID の ID Token を検証（RS256）
        1. JWKS エンドポイントから公開鍵を取得
        2. kid（Key ID）で対応する公開鍵を選択
        3. RS256 署名を検証
        4. クレームを検証（issuer, audience, expiry）
        """
        signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)

        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.client_id,
            issuer=f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )
```

### 鍵ローテーション

```python
# JWT シークレットキーのローテーション計画
ROTATION_CONFIG = {
    "hs256_secret": {
        "rotation_interval_days": 90,  # 90日ごとにローテーション
        "grace_period_hours": 24,      # 旧キーを 24時間有効に維持
    },
    "rs256_private_key": {
        "rotation_interval_days": 365, # 1年ごとにローテーション
        "key_size_bits": 4096,         # RSA キー長
        "grace_period_hours": 48,      # 旧公開鍵を 48時間公開維持
    }
}

# ローテーション時は Key Vault のバージョン管理を活用
# 旧バージョンは grace_period 後に無効化
```

---

## データベース暗号化

### PostgreSQL TDE（Transparent Data Encryption）

```sql
-- PostgreSQL 暗号化設定
-- pgcrypto 拡張を使用したフィールドレベル暗号化

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- PII フィールドを暗号化して保存する例
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 暗号化フィールド（AES-256）
    email_encrypted BYTEA NOT NULL,      -- メールアドレス（暗号化）
    phone_encrypted BYTEA,               -- 電話番号（暗号化）
    -- 検索用ハッシュ（暗号化フィールドの等値検索用）
    email_hash TEXT GENERATED ALWAYS AS (
        encode(digest(email_encrypted::text, 'sha256'), 'hex')
    ) STORED,
    -- 非暗号化フィールド
    display_name TEXT NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 暗号化して挿入
INSERT INTO users (email_encrypted, display_name, tenant_id)
VALUES (
    pgp_sym_encrypt(
        'user@example.com',
        current_setting('app.encryption_key')  -- Key Vault から取得したキー
    ),
    '山田 太郎',
    '550e8400-e29b-41d4-a716-446655440000'
);

-- 復号して取得
SELECT
    pgp_sym_decrypt(email_encrypted, current_setting('app.encryption_key')) AS email,
    display_name
FROM users
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000';
```

### Azure SQL / PostgreSQL TDE 設定

```
Azure Database for PostgreSQL の Transparent Data Encryption:

有効化手順:
1. Azure Portal → PostgreSQL サーバー → セキュリティ → データ暗号化
2. 暗号化の種類: 顧客管理キー（CMK）を選択
3. Azure Key Vault のキー URI を指定
4. TDE が自動的に全データファイル・ログファイルを暗号化

暗号化対象:
  - データファイル（.mdf, .ndf）
  - ログファイル（.ldf）
  - バックアップファイル
  - tempdb

アルゴリズム: AES-256

CMK（顧客管理キー）のメリット:
  - 完全なキー制御権を保持
  - BYOK（Bring Your Own Key）対応
  - キーの独立した失効・ローテーションが可能
  - コンプライアンス要件への対応（FIPS 140-2 Level 2/3）
```

### 行レベルセキュリティ（RLS）

```sql
-- PostgreSQL 行レベルセキュリティ（テナント分離）
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- テナント分離ポリシー
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 管理者は全テナントにアクセス可能
CREATE POLICY admin_bypass ON users
    USING (current_setting('app.is_global_admin')::BOOLEAN = true);

-- FastAPI からテナント ID をセッション変数に設定
-- db.execute("SET app.current_tenant_id = ?", [tenant_id])
```

---

## シークレット管理（Azure Key Vault）

### Key Vault 管理対象

| シークレット種別 | Key Vault 名 | ローテーション周期 | アクセス制御 |
|---------------|-------------|-----------------|------------|
| JWT シークレットキー | `jwt-secret-key` | 90日 | バックエンドサービスのみ |
| DB 接続文字列 | `db-connection-string` | パスワード変更時 | バックエンドサービスのみ |
| DB 暗号化キー | `db-encryption-key` | 1年 | バックエンドサービスのみ |
| Azure EntraID クライアントシークレット | `entra-client-secret` | 1年 | バックエンドサービスのみ |
| 外部 API キー | `external-api-key-*` | 90日 | 該当サービスのみ |
| SMTP 認証情報 | `smtp-credentials` | 90日 | 通知サービスのみ |
| バックアップ暗号化キー | `backup-encryption-key` | 1年 | バックアップサービスのみ |

### Key Vault アクセス実装

```python
# Azure Key Vault へのアクセス（Managed Identity を使用）
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from functools import lru_cache
import os

class KeyVaultService:
    """
    Azure Key Vault へのアクセスを管理するサービス
    Managed Identity を使用することで、クレデンシャルをコードに含めない
    """

    def __init__(self):
        self.vault_url = os.environ["AZURE_KEY_VAULT_URL"]
        # Managed Identity（本番） または DefaultAzureCredential（開発）
        self.credential = ManagedIdentityCredential()
        self.secret_client = SecretClient(
            vault_url=self.vault_url,
            credential=self.credential
        )
        self.key_client = KeyClient(
            vault_url=self.vault_url,
            credential=self.credential
        )

    @lru_cache(maxsize=None)
    def get_secret(self, secret_name: str) -> str:
        """
        シークレットを取得（メモリキャッシュ付き）
        TTL なしのキャッシュ：アプリ再起動でクリア
        """
        secret = self.secret_client.get_secret(secret_name)
        return secret.value

    async def rotate_secret(self, secret_name: str, new_value: str) -> None:
        """
        シークレットをローテーション
        1. 新しいバージョンを Key Vault に保存
        2. 旧バージョンを一定期間後に無効化（grace period）
        """
        self.secret_client.set_secret(secret_name, new_value)
        # キャッシュをクリア
        self.get_secret.cache_clear()

# Key Vault アクセスポリシー設定
KEY_VAULT_ACCESS_POLICY = {
    "backend_service": {
        "secrets": ["get", "list"],  # 読み取りのみ
        "keys": [],
        "certificates": []
    },
    "security_admin": {
        "secrets": ["get", "list", "set", "delete", "backup", "restore"],
        "keys": ["get", "list", "create", "delete", "rotate"],
        "certificates": ["get", "list", "create", "delete"]
    }
}
```

### シークレットローテーション自動化

```yaml
# Azure Key Vault ローテーションポリシー（Bicep / ARM）
resource jwtSecretRotation 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'jwt-secret-key'
  properties: {
    rotationPolicy: {
      lifetimeActions: [
        {
          trigger: {
            timeBeforeExpiry: 'P7D'  # 期限7日前に通知
          }
          action: {
            type: 'Notify'
          }
        }
        {
          trigger: {
            timeAfterCreate: 'P90D'  # 作成から90日後にローテーション
          }
          action: {
            type: 'Rotate'
          }
        }
      ]
    }
  }
}
```

---

## パスワードハッシュ（bcrypt）

### bcrypt 設計仕様

```python
# passlib を使用した bcrypt 実装
from passlib.context import CryptContext
from passlib.hash import bcrypt as bcrypt_hash
import time

# bcrypt コストファクター設定
# セキュリティと UX のバランスを考慮
BCRYPT_CONFIG = {
    "rounds": 12,          # コストファクター（約 400ms on 2024 hardware）
    "ident": "2b",         # bcrypt バージョン（最新の 2b を使用）
}

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_CONFIG["rounds"],
    bcrypt__ident=BCRYPT_CONFIG["ident"]
)

class PasswordService:

    def hash_password(self, plain_password: str) -> str:
        """パスワードを bcrypt でハッシュ化"""
        return pwd_context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワードを検証（タイミング攻撃耐性あり）"""
        return pwd_context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        コストファクターが変更された場合に再ハッシュが必要か確認
        ログイン成功時にサイレントに再ハッシュ
        """
        return pwd_context.needs_update(hashed_password)

    def measure_hash_time(self) -> float:
        """ハッシュ処理時間を計測（性能チューニング用）"""
        start = time.time()
        self.hash_password("benchmark_password_12345!")
        return time.time() - start

# bcrypt コストファクターの選定基準:
# 目標: ハッシュ処理に 200ms〜1000ms かかるコストを選択
# rounds=10: ~100ms  （最低ライン）
# rounds=12: ~400ms  ← 推奨
# rounds=14: ~1600ms （UX に影響する可能性）
```

### パスワード強度チェック

```python
from zxcvbn import zxcvbn

def check_password_strength(password: str, user_inputs: list[str] = []) -> dict:
    """
    zxcvbn ライブラリによる パスワード強度評価
    スコア 0-4:
      0: Very Weak（禁止）
      1: Weak（禁止）
      2: Fair（禁止）
      3: Good（許可）← 最低スコア
      4: Strong（推奨）
    """
    result = zxcvbn(password, user_inputs=user_inputs)

    if result["score"] < 3:
        raise WeakPasswordException(
            f"パスワードが脆弱です（スコア: {result['score']}/4）。"
            f"提案: {result['feedback']['suggestions']}"
        )

    return {
        "score": result["score"],
        "crack_time": result["crack_times_display"]["offline_slow_hashing_1e4_per_second"],
        "feedback": result["feedback"]
    }
```

---

## 監査ログの改ざん防止

### SHA-256 ハッシュチェーン設計

```
監査ログの改ざん防止のため、ブロックチェーン的なハッシュチェーンを採用。
各ログエントリは前のエントリのハッシュを含み、連鎖的な整合性を保証する。

Log Entry N:
  ├── id: UUID
  ├── timestamp: TIMESTAMPTZ
  ├── event_type: string
  ├── user_id: UUID
  ├── resource: string
  ├── action: string
  ├── result: "allow" | "deny"
  ├── metadata: JSONB
  ├── previous_hash: SHA-256（前エントリのハッシュ）← チェーンのリンク
  └── entry_hash: SHA-256（このエントリ全体のハッシュ）
```

### ハッシュチェーン実装

```python
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

class AuditLogService:

    def compute_entry_hash(self, entry: dict, previous_hash: str) -> str:
        """
        ログエントリのハッシュを計算
        previous_hash を含めることで改ざん検知を実現
        """
        content = {
            "id": str(entry["id"]),
            "timestamp": entry["timestamp"].isoformat(),
            "event_type": entry["event_type"],
            "user_id": str(entry["user_id"]),
            "resource": entry["resource"],
            "action": entry["action"],
            "result": entry["result"],
            "previous_hash": previous_hash
        }
        # JSON をシリアライズ（キーの順序を固定）
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    async def record(self, **kwargs) -> dict:
        """
        監査ログを記録
        1. 直前のログエントリのハッシュを取得
        2. 新しいエントリのハッシュを計算
        3. DB に保存（削除・更新は禁止）
        """
        # 直前エントリのハッシュを取得
        previous_entry = await self.get_latest_entry()
        previous_hash = previous_entry["entry_hash"] if previous_entry else "0" * 64

        # エントリを構築
        entry = {
            "id": uuid4(),
            "timestamp": datetime.now(timezone.utc),
            **kwargs,
            "previous_hash": previous_hash,
        }

        # ハッシュを計算
        entry["entry_hash"] = self.compute_entry_hash(entry, previous_hash)

        # DB に挿入（UPDATE / DELETE は禁止）
        await self.db.execute("""
            INSERT INTO audit_logs (
                id, timestamp, event_type, user_id, resource, action,
                result, metadata, previous_hash, entry_hash
            ) VALUES (
                :id, :timestamp, :event_type, :user_id, :resource, :action,
                :result, :metadata, :previous_hash, :entry_hash
            )
        """, entry)

        return entry

    async def verify_chain_integrity(
        self,
        start_id: UUID = None,
        limit: int = 1000
    ) -> dict:
        """
        ハッシュチェーンの整合性を検証
        改ざんがあれば検知できる
        """
        entries = await self.get_entries_ordered(start_id, limit)
        errors = []

        for i, entry in enumerate(entries):
            if i == 0:
                previous_hash = "0" * 64  # ジェネシスエントリ
            else:
                previous_hash = entries[i - 1]["entry_hash"]

            # ハッシュを再計算して比較
            computed_hash = self.compute_entry_hash(entry, previous_hash)

            if computed_hash != entry["entry_hash"]:
                errors.append({
                    "entry_id": str(entry["id"]),
                    "timestamp": entry["timestamp"].isoformat(),
                    "issue": "ハッシュ不整合 - 改ざんの可能性",
                    "stored_hash": entry["entry_hash"],
                    "computed_hash": computed_hash
                })

        return {
            "total_checked": len(entries),
            "integrity_ok": len(errors) == 0,
            "errors": errors,
            "verified_at": datetime.now(timezone.utc).isoformat()
        }
```

### 監査ログ DB テーブル設計

```sql
-- 監査ログテーブル（改ざん防止設計）
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    user_id UUID REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('allow', 'deny', 'error')),
    source_ip INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',

    -- ハッシュチェーン
    previous_hash TEXT NOT NULL,      -- 前エントリの SHA-256 ハッシュ
    entry_hash TEXT NOT NULL UNIQUE,  -- このエントリの SHA-256 ハッシュ

    -- インデックス用フィールド
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 削除・更新を禁止するトリガー
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '監査ログの変更・削除は禁止されています（改ざん防止ポリシー）';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER protect_audit_logs
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();

-- 読み取り最適化インデックス
CREATE INDEX idx_audit_logs_user_id ON audit_logs (user_id, timestamp DESC);
CREATE INDEX idx_audit_logs_tenant_id ON audit_logs (tenant_id, timestamp DESC);
CREATE INDEX idx_audit_logs_event_type ON audit_logs (event_type, timestamp DESC);
```

---

## 暗号化アルゴリズム一覧

| 用途 | アルゴリズム | 鍵長 | 理由 |
|------|------------|------|------|
| 通信暗号化 | TLS 1.3（AES-256-GCM） | 256bit | NIST 推奨・PFS 確保 |
| JWT 署名（内部） | HMAC-SHA256（HS256） | 256bit | 高速・シンプル |
| JWT 署名（外部） | RSA-SHA256（RS256） | 4096bit | 非対称・検証可能 |
| DB フィールド暗号化 | AES-256-GCM | 256bit | 認証付き暗号化 |
| DB 全体暗号化 | AES-256（TDE） | 256bit | FIPS 140-2 準拠 |
| パスワードハッシュ | bcrypt（cost=12） | - | ブルートフォース耐性 |
| 監査ログハッシュ | SHA-256 | 256bit | 改ざん検知 |
| 乱数生成 | CSPRNG（secrets モジュール） | 256bit | 暗号論的安全乱数 |

---

## 改訂履歴

| バージョン | 日付 | 変更内容 | 変更者 |
|-----------|------|---------|--------|
| 1.0.0 | 2026-03-24 | 初版作成 | セキュリティ開発チーム |
