# HENGEONE 連携設計（HENGEONE Integration）

| 項目 | 内容 |
|------|------|
| 文書番号 | INT-HEN-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新日 | 2026-03-24 |
| 作成者 | アーキテクチャチーム |
| ステータス | ドラフト |
| 関連システム | HENGEONE（株式会社ヘッジホッグ・テック） |

---

## 1. 概要

本文書は、ZeroTrust-ID-Governance システムと HENGEONE（クラウド IDaaS プラットフォーム）との統合設計を定義する。
HENGEONE は日本のオンプレミス Active Directory とクラウドサービスを統合するIDaaS ソリューションであり、
REST API を通じてユーザーアカウントのプロビジョニング・デプロビジョニング・同期を行う。

### 1.1 統合目標

- HENGEONE へのユーザーアカウント自動プロビジョニング
- `hengeone_id` によるユーザーの一意紐付け
- ライフサイクルイベント（入社・異動・退職）に応じた自動アカウント管理
- HENGEONE を経由したクラウドサービス（Microsoft 365・Google Workspace 等）へのアクセス権管理

### 1.2 HENGEONE の役割

```
ZeroTrust-ID-Governance
        │
        │  REST API（プロビジョニング）
        ▼
    HENGEONE IDaaS
        │
        ├── Microsoft 365
        ├── Google Workspace
        ├── Box
        ├── Salesforce
        └── その他 SaaS
```

---

## 2. API キー認証

### 2.1 認証方式

HENGEONE API はリクエストヘッダーに API キーを付与する方式で認証を行う。

```http
GET /api/v1/users HTTP/1.1
Host: api.hengeone.example.com
X-API-Key: your-hengeone-api-key
Content-Type: application/json
Accept: application/json
```

### 2.2 環境変数設定

```bash
# HENGEONE 接続設定
HENGEONE_API_KEY=your-hengeone-api-key
HENGEONE_BASE_URL=https://api.hengeone.example.com
HENGEONE_API_VERSION=v1
HENGEONE_TIMEOUT=30
HENGEONE_MAX_RETRIES=3
```

### 2.3 API キー管理方針

| 項目 | 方針 |
|------|------|
| 保存方法 | 環境変数またはシークレット管理システム（Vault 等） |
| ローテーション | 90日ごとに定期更新 |
| スコープ | 最小権限（ユーザー管理のみ） |
| 監査 | 全 API 呼び出しをアクセスログに記録 |
| 漏洩時対応 | 即時無効化 → 新規キー発行 → アラート通知 |

---

## 3. ユーザーアカウント管理 API 呼び出し

### 3.1 HENGEONE API クライアント実装

```python
# integrations/hengeone/client.py
import httpx
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class HengeOneClient:
    """HENGEONE REST API クライアント"""

    def __init__(self):
        self.base_url = settings.HENGEONE_BASE_URL.rstrip("/")
        self.api_version = settings.HENGEONE_API_VERSION
        self.api_key = settings.HENGEONE_API_KEY
        self.timeout = int(settings.HENGEONE_TIMEOUT)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/{self.api_version}/{path.lstrip('/')}"

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def list_users(self, page: int = 1, per_page: int = 100) -> dict:
        """ユーザー一覧取得"""
        response = httpx.get(
            self._url("users"),
            headers=self._headers(),
            params={"page": page, "per_page": per_page},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_user(self, hengeone_id: str) -> dict:
        """特定ユーザー取得"""
        response = httpx.get(
            self._url(f"users/{hengeone_id}"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def create_user(self, user_data: dict) -> dict:
        """ユーザーアカウント作成"""
        response = httpx.post(
            self._url("users"),
            json=user_data,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def update_user(self, hengeone_id: str, user_data: dict) -> dict:
        """ユーザーアカウント更新"""
        response = httpx.patch(
            self._url(f"users/{hengeone_id}"),
            json=user_data,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def disable_user(self, hengeone_id: str) -> dict:
        """ユーザーアカウント無効化"""
        return self.update_user(hengeone_id, {"status": "disabled"})

    def delete_user(self, hengeone_id: str) -> None:
        """ユーザーアカウント削除"""
        response = httpx.delete(
            self._url(f"users/{hengeone_id}"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
```

### 3.2 主要 API エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| `GET` | `/api/v1/users` | ユーザー一覧取得（ページング対応） |
| `GET` | `/api/v1/users/{id}` | 特定ユーザー取得 |
| `POST` | `/api/v1/users` | ユーザーアカウント作成 |
| `PATCH` | `/api/v1/users/{id}` | ユーザーアカウント部分更新 |
| `PUT` | `/api/v1/users/{id}` | ユーザーアカウント全量更新 |
| `DELETE` | `/api/v1/users/{id}` | ユーザーアカウント削除 |
| `POST` | `/api/v1/users/{id}/disable` | ユーザー無効化 |
| `POST` | `/api/v1/users/{id}/enable` | ユーザー有効化 |

### 3.3 リクエスト / レスポンス形式

**ユーザー作成リクエスト例:**

```json
{
  "loginId": "yamada.taro",
  "email": "yamada.taro@example.com",
  "lastName": "山田",
  "firstName": "太郎",
  "lastNameKana": "ヤマダ",
  "firstNameKana": "タロウ",
  "displayName": "山田 太郎",
  "department": "情報システム部",
  "jobTitle": "エンジニア",
  "status": "active",
  "externalId": "zt-user-12345"
}
```

**ユーザー作成レスポンス例:**

```json
{
  "id": "hen-abc123def456",
  "loginId": "yamada.taro",
  "email": "yamada.taro@example.com",
  "lastName": "山田",
  "firstName": "太郎",
  "displayName": "山田 太郎",
  "department": "情報システム部",
  "status": "active",
  "externalId": "zt-user-12345",
  "createdAt": "2026-03-24T10:00:00+09:00",
  "updatedAt": "2026-03-24T10:00:00+09:00"
}
```

---

## 4. hengeone_id によるユーザー紐付け

### 4.1 データモデル

```python
# users/models.py（抜粋）
class User(AbstractBaseUser):
    # HENGEONE 連携フィールド
    hengeone_id = models.CharField(
        max_length=256,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="HENGEONE ユーザー ID",
    )
    hengeone_provisioning_status = models.CharField(
        max_length=20,
        choices=ProvisioningStatus.choices,
        default=ProvisioningStatus.PENDING,
    )
    hengeone_last_synced_at = models.DateTimeField(null=True, blank=True)
```

### 4.2 ユーザー照合ロジック

```python
def find_or_create_from_hengeone(hengeone_data: dict):
    """
    HENGEONE データから ZeroTrust ユーザーを検索または作成する
    照合優先順位: hengeone_id > externalId > email
    """
    hengeone_id = hengeone_data.get("id")
    external_id = hengeone_data.get("externalId")  # ZeroTrust の user_id
    email = hengeone_data.get("email")

    # 1. hengeone_id で検索
    user = User.objects.filter(hengeone_id=hengeone_id).first()
    if user:
        return user

    # 2. externalId（ZeroTrust user PK）で検索
    if external_id and external_id.startswith("zt-user-"):
        pk = external_id.replace("zt-user-", "")
        user = User.objects.filter(pk=pk).first()
        if user:
            user.hengeone_id = hengeone_id
            user.save(update_fields=["hengeone_id"])
            return user

    # 3. メールアドレスで検索
    if email:
        user = User.objects.filter(email=email).first()
        if user:
            user.hengeone_id = hengeone_id
            user.save(update_fields=["hengeone_id"])
            return user

    return None
```

---

## 5. プロビジョニング / デプロビジョニングフロー

```mermaid
flowchart TD
    subgraph Provisioning["プロビジョニングフロー"]
        P_Start([ユーザー作成イベント])
        P_Start --> P_Check{ZeroTrust DB に\nユーザー存在?}
        P_Check -->|No| P_Error([エラー: ユーザー未存在])
        P_Check -->|Yes| P_HEN_Check{HENGEONE に\n既存アカウント?}
        P_HEN_Check -->|Yes| P_Update[既存アカウントを更新\nPATCH /users/{id}]
        P_HEN_Check -->|No| P_Create[新規アカウント作成\nPOST /users]
        P_Create --> P_Success{作成成功?}
        P_Update --> P_Success
        P_Success -->|Yes| P_Save[hengeone_id を DB 保存]
        P_Save --> P_Log[プロビジョニングログ記録]
        P_Log --> P_Done([完了])
        P_Success -->|No| P_Retry{再試行回数\n< 3?}
        P_Retry -->|Yes| P_Wait[指数バックオフ待機] --> P_Create
        P_Retry -->|No| P_DLQ[DLQ に移動\nアラート発報]
        P_DLQ --> P_Error
    end

    subgraph Deprovisioning["デプロビジョニングフロー"]
        D_Start([ユーザー無効化イベント])
        D_Start --> D_Check{hengeone_id\n存在?}
        D_Check -->|No| D_Skip[スキップ\nログ記録]
        D_Check -->|Yes| D_Disable[アカウント無効化\nPOST /users/{id}/disable]
        D_Disable --> D_Success{成功?}
        D_Success -->|Yes| D_Update[DB ステータス更新\nDEPROVISIONED]
        D_Update --> D_Log[デプロビジョニングログ記録]
        D_Log --> D_Done([完了])
        D_Success -->|No| D_Retry{再試行回数\n< 3?}
        D_Retry -->|Yes| D_Wait[指数バックオフ待機] --> D_Disable
        D_Retry -->|No| D_DLQ[DLQ に移動\nアラート発報]
        D_DLQ --> D_Skip
    end
```

### 5.1 プロビジョニング実装

```python
# integrations/hengeone/provisioning.py
from integrations.hengeone.client import HengeOneClient
from django.utils import timezone


def provision_user_to_hengeone(user) -> str:
    """
    ZeroTrust ユーザーを HENGEONE に作成し、hengeone_id を返す
    """
    client = HengeOneClient()

    payload = {
        "loginId": user.username,
        "email": user.email,
        "lastName": user.last_name,
        "firstName": user.first_name,
        "displayName": user.get_full_name(),
        "department": getattr(user, "department", ""),
        "jobTitle": getattr(user, "job_title", ""),
        "status": "active",
        "externalId": f"zt-user-{user.pk}",
    }

    # 既存アカウント確認（冪等性保証）
    existing = _find_existing_hengeone_user(client, user)
    if existing:
        result = client.update_user(existing["id"], payload)
        hengeone_id = existing["id"]
    else:
        result = client.create_user(payload)
        hengeone_id = result["id"]

    # DB に保存
    user.hengeone_id = hengeone_id
    user.hengeone_provisioning_status = "PROVISIONED"
    user.hengeone_last_synced_at = timezone.now()
    user.save(update_fields=[
        "hengeone_id",
        "hengeone_provisioning_status",
        "hengeone_last_synced_at",
    ])
    return hengeone_id


def deprovision_user_from_hengeone(user) -> None:
    """HENGEONE ユーザーを無効化する"""
    if not user.hengeone_id:
        return

    client = HengeOneClient()
    client.disable_user(user.hengeone_id)

    user.hengeone_provisioning_status = "DEPROVISIONED"
    user.save(update_fields=["hengeone_provisioning_status"])
```

---

## 6. エラー処理とリトライ

### 6.1 エラー種別と対応方針

| HTTP ステータス | エラー内容 | 対応方針 |
|--------------|-----------|---------|
| `400 Bad Request` | リクエストパラメータ不正 | リトライなし、エラーログ記録、アラート |
| `401 Unauthorized` | API キー無効 | リトライなし、緊急アラート、API キー確認 |
| `403 Forbidden` | 権限不足 | リトライなし、アラート |
| `404 Not Found` | ユーザー未存在 | 作成処理に切り替え |
| `409 Conflict` | リソース重複 | 更新処理に切り替え |
| `422 Unprocessable Entity` | バリデーションエラー | リトライなし、詳細ログ記録 |
| `429 Too Many Requests` | レートリミット超過 | `Retry-After` ヘッダーの秒数待機後リトライ |
| `500 Internal Server Error` | HENGEONE サーバーエラー | 指数バックオフでリトライ（最大 3回） |
| `503 Service Unavailable` | サービス停止中 | 指数バックオフでリトライ（最大 5回） |

### 6.2 リトライ実装

```python
# integrations/hengeone/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
import httpx

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="integration",
)
def provision_user_hengeone_task(self, user_id: int):
    """HENGEONE ユーザープロビジョニング Celery タスク"""
    from users.models import User
    from integrations.hengeone.provisioning import provision_user_to_hengeone

    try:
        user = User.objects.get(pk=user_id)
        provision_user_to_hengeone(user)
        logger.info(f"HENGEONE プロビジョニング成功: user_id={user_id}")

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code

        if status_code == 429:
            # レートリミット: Retry-After に従う
            retry_after = int(exc.response.headers.get("Retry-After", 60))
            raise self.retry(exc=exc, countdown=retry_after)

        elif status_code in (500, 502, 503, 504):
            # サーバーエラー: 指数バックオフ
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

        elif status_code == 409:
            # 重複: 更新処理に切り替え
            logger.warning(f"HENGEONE 重複検知、更新に切り替え: user_id={user_id}")
            _handle_conflict_update(user_id)

        else:
            # 4xx エラー: リトライ不要
            logger.error(f"HENGEONE プロビジョニング失敗（4xx）: user_id={user_id}, status={status_code}")
            _record_failure(user_id, str(exc))
            raise

    except Exception as exc:
        logger.error(f"HENGEONE プロビジョニング予期しないエラー: user_id={user_id}, error={exc}")
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
```

### 6.3 レートリミット対策

| 項目 | 設定値 |
|------|--------|
| HENGEONE API レート上限 | 100 リクエスト / 分（想定） |
| Celery 同時実行ワーカー数 | 最大 5 |
| バースト時の待機戦略 | `Retry-After` ヘッダー準拠 |
| バッチ処理の間隔 | 200ms ごとに 1 リクエスト |

```python
import time

def batch_sync_all_users():
    """全ユーザーの HENGEONE 同期（レートリミット対応）"""
    client = HengeOneClient()
    users = User.objects.filter(
        hengeone_provisioning_status="PROVISIONED"
    ).iterator(chunk_size=100)

    for user in users:
        try:
            _sync_single_user(client, user)
            time.sleep(0.2)  # 200ms 間隔
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                retry_after = int(exc.response.headers.get("Retry-After", 60))
                logger.warning(f"レートリミット到達、{retry_after}秒待機")
                time.sleep(retry_after)
```

---

## 7. 関連文書

| 文書番号 | 文書名 |
|---------|-------|
| INT-OVR-001 | 外部システム連携概要 |
| INT-ENT-001 | EntraID 連携設計 |
| INT-AD-001 | Active Directory 連携設計 |
| INT-WH-001 | Webhook 設計 |
| SEC-001 | セキュリティ設計概要 |
