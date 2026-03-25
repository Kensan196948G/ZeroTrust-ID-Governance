# Webhook 設計（Webhook Design）

| 項目 | 内容 |
|------|------|
| 文書番号 | INT-WH-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新日 | 2026-03-24 |
| 作成者 | アーキテクチャチーム |
| ステータス | ドラフト |
| 関連システム | EntraID / HENGEONE / 汎用外部システム |

---

## 1. 概要

本文書は、ZeroTrust-ID-Governance システムが外部システム（Azure Entra ID・HENGEONE 等）から受信する Webhook のエンドポイント設計、セキュリティ、ペイロード形式、リトライポリシー、冪等性設計、および実装例を定義する。

### 1.1 Webhook の目的

- 外部システムでのイベント（ユーザー作成・更新・削除・ロール変更等）を受信し、ZeroTrust-ID-Governance のユーザーデータをリアルタイムに反映する
- バッチ同期では対応できない即時性が必要なイベントに対応する
- 冪等な処理設計により、重複配信に対してもデータ整合性を保証する

### 1.2 Webhook エンドポイント一覧

| エンドポイント | メソッド | 送信元システム | 説明 |
|--------------|---------|-------------|------|
| `/api/v1/webhooks/entra/` | `POST` | Azure Entra ID | EntraID イベント受信 |
| `/api/v1/webhooks/hengeone/` | `POST` | HENGEONE | HENGEONE イベント受信 |
| `/api/v1/webhooks/generic/` | `POST` | 汎用外部システム | 汎用 Webhook 受信 |

---

## 2. イベントタイプ一覧

### 2.1 ユーザーライフサイクルイベント

| イベントタイプ | 説明 | 優先度 | 処理タイムアウト |
|-------------|------|--------|---------------|
| `user.created` | ユーザーが外部システムで新規作成された | 高 | 60秒 |
| `user.updated` | ユーザー情報が更新された | 中 | 60秒 |
| `user.deleted` | ユーザーが削除された | 高 | 60秒 |
| `user.enabled` | ユーザーアカウントが有効化された | 高 | 30秒 |
| `user.disabled` | ユーザーアカウントが無効化された | 高 | 30秒 |
| `user.password_changed` | パスワードが変更された | 中 | 30秒 |
| `user.mfa_updated` | MFA 設定が変更された | 中 | 30秒 |

### 2.2 グループ / ロールイベント

| イベントタイプ | 説明 | 優先度 | 処理タイムアウト |
|-------------|------|--------|---------------|
| `user.role_assigned` | ユーザーにロールが付与された | 高 | 30秒 |
| `user.role_removed` | ユーザーからロールが削除された | 高 | 30秒 |
| `group.member_added` | グループにメンバーが追加された | 中 | 30秒 |
| `group.member_removed` | グループからメンバーが削除された | 中 | 30秒 |
| `group.created` | グループが作成された | 低 | 60秒 |
| `group.deleted` | グループが削除された | 中 | 60秒 |

### 2.3 セキュリティイベント

| イベントタイプ | 説明 | 優先度 | 処理タイムアウト |
|-------------|------|--------|---------------|
| `user.login_failed` | ログイン失敗（閾値超過） | 高 | 15秒 |
| `user.account_locked` | アカウントがロックされた | 高 | 15秒 |
| `user.suspicious_activity` | 不審なアクティビティ検知 | 緊急 | 15秒 |

---

## 3. Webhook セキュリティ（シグネチャ検証）

### 3.1 HMAC-SHA256 シグネチャ検証

外部システムは各 Webhook リクエストのペイロードを HMAC-SHA256 で署名し、シグネチャをリクエストヘッダーに付与する。
ZeroTrust-ID-Governance はこのシグネチャを検証することで、リクエストの正当性を確認する。

```
# リクエストヘッダー
X-Webhook-Signature: sha256=abc123def456...
X-Webhook-Timestamp: 1711234567
X-Webhook-Delivery-ID: uuid-v4-delivery-id
X-Webhook-Event: user.created
X-Webhook-Source: entra  # または hengeone
```

### 3.2 シグネチャ検証実装

```python
# webhooks/security.py
import hashlib
import hmac
import time
from django.conf import settings
from django.core.exceptions import SuspiciousOperation


# 許容するタイムスタンプのずれ（秒）
TIMESTAMP_TOLERANCE = 300  # 5分


def verify_webhook_signature(
    payload_body: bytes,
    signature_header: str,
    timestamp_header: str,
    secret: str,
) -> None:
    """
    Webhook シグネチャを検証する。
    検証失敗時は SuspiciousOperation を送出する。
    """
    # 1. タイムスタンプ検証（リプレイアタック防止）
    try:
        timestamp = int(timestamp_header)
    except (ValueError, TypeError):
        raise SuspiciousOperation("無効なタイムスタンプ")

    current_time = int(time.time())
    if abs(current_time - timestamp) > TIMESTAMP_TOLERANCE:
        raise SuspiciousOperation(
            f"タイムスタンプ許容範囲外: diff={abs(current_time - timestamp)}秒"
        )

    # 2. HMAC-SHA256 シグネチャ検証
    # 署名対象: "{timestamp}.{payload_body}"
    signed_content = f"{timestamp}.".encode() + payload_body
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signed_content,
        hashlib.sha256,
    ).hexdigest()
    expected_header = f"sha256={expected_signature}"

    # タイミング攻撃防止のための定数時間比較
    if not hmac.compare_digest(signature_header, expected_header):
        raise SuspiciousOperation("シグネチャ検証失敗")
```

### 3.3 送信元 IP 許可リスト

| システム | 許可 IP レンジ | 備考 |
|---------|-------------|------|
| Azure Entra ID | Microsoft の公開 IP レンジ | ServiceTag: AzureActiveDirectory |
| HENGEONE | HENGEONE が指定する固定 IP | 事前に取得・登録 |

```python
# settings.py
WEBHOOK_ALLOWED_IPS = {
    "entra": [
        # Azure AD Webhook IP レンジ（例）
        "40.126.0.0/18",
        "20.190.128.0/18",
    ],
    "hengeone": [
        "203.0.113.10/32",   # HENGEONE 送信元 IP（例）
        "203.0.113.11/32",
    ],
}
```

---

## 4. ペイロード形式（JSON）

### 4.1 標準ペイロード構造

```json
{
  "id": "wh-evt-550e8400-e29b-41d4-a716-446655440000",
  "event": "user.created",
  "source": "entra",
  "timestamp": "2026-03-24T10:00:00.000Z",
  "api_version": "2026-03-01",
  "data": {
    "user": {
      "id": "entra-object-id-or-hengeone-id",
      "email": "yamada.taro@example.com",
      "username": "yamada.taro",
      "first_name": "太郎",
      "last_name": "山田",
      "display_name": "山田 太郎",
      "department": "情報システム部",
      "job_title": "エンジニア",
      "status": "active",
      "external_id": "zt-user-12345"
    }
  },
  "metadata": {
    "retry_count": 0,
    "original_delivery_id": "wh-evt-550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 4.2 イベント別ペイロード例

**`user.role_assigned` イベント:**

```json
{
  "id": "wh-evt-uuid",
  "event": "user.role_assigned",
  "source": "entra",
  "timestamp": "2026-03-24T10:05:00.000Z",
  "data": {
    "user": {
      "id": "entra-object-id",
      "email": "yamada.taro@example.com"
    },
    "role": {
      "id": "entra-role-id",
      "name": "IT-Admins",
      "display_name": "IT 管理者"
    }
  }
}
```

**`user.disabled` イベント:**

```json
{
  "id": "wh-evt-uuid",
  "event": "user.disabled",
  "source": "hengeone",
  "timestamp": "2026-03-24T10:10:00.000Z",
  "data": {
    "user": {
      "id": "hen-abc123def456",
      "email": "yamada.taro@example.com",
      "reason": "退職"
    }
  }
}
```

---

## 5. リトライポリシー

### 5.1 ZeroTrust からの Webhook レスポンス仕様

外部システムからの Webhook を受信した ZeroTrust は、以下のレスポンスルールに従う。

| ステータスコード | 意味 | 外部システムの動作 |
|--------------|------|----------------|
| `200 OK` | 受信・処理成功 | リトライなし |
| `202 Accepted` | 受信確認（非同期処理） | リトライなし |
| `400 Bad Request` | ペイロード不正 | リトライなし（設定エラーの可能性） |
| `401 Unauthorized` | 認証失敗 | リトライなし（設定要確認） |
| `409 Conflict` | 重複イベント（冪等処理済み） | リトライなし |
| `500 Internal Server Error` | 処理失敗 | リトライあり |
| `503 Service Unavailable` | サービス停止中 | リトライあり |

### 5.2 外部システムへのリトライ期待値

ZeroTrust がダウンしていた場合、外部システムからのリトライを以下の条件で受け入れる。

| リトライ回数 | 待機時間（例） | 最大待機合計 |
|-----------|-----------|-----------|
| 1回目 | 即時 | - |
| 2回目 | 1分後 | 1分 |
| 3回目 | 5分後 | 6分 |
| 4回目 | 30分後 | 36分 |
| 5回目 | 2時間後 | 2時間36分 |
| 最終リトライ | 24時間後 | 約27時間 |

---

## 6. 冪等性設計

### 6.1 冪等性の保証方針

Webhook は配信保証（at-least-once delivery）のため、同一イベントが複数回配信される可能性がある。
ZeroTrust は以下の設計により冪等性を保証する。

1. **配信 ID（delivery_id）によるキー管理**: 同一 `id` のイベントは処理をスキップ
2. **べき等性を持つ操作**: PATCH / PUT による更新は同じデータで複数回実行しても結果が変わらない
3. **外部 ID による存在確認**: プロビジョニング前に必ず外部システムへの登録有無を確認する

### 6.2 冪等性実装

```python
# webhooks/models.py
class WebhookEvent(models.Model):
    """受信 Webhook イベントの記録（冪等性保証用）"""

    delivery_id = models.CharField(
        max_length=256,
        unique=True,
        db_index=True,
        help_text="Webhook 配信 ID（X-Webhook-Delivery-ID）",
    )
    event_type = models.CharField(max_length=100)
    source = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("RECEIVED", "受信"),
            ("PROCESSING", "処理中"),
            ("PROCESSED", "処理完了"),
            ("SKIPPED", "スキップ（重複）"),
            ("FAILED", "失敗"),
        ],
        default="RECEIVED",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "webhook_events"
        indexes = [
            models.Index(fields=["delivery_id"]),
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["received_at"]),
        ]
```

```python
# webhooks/views.py
from django.db import IntegrityError
from django.utils import timezone


def process_webhook_idempotent(delivery_id: str, event_type: str, source: str, payload: dict):
    """冪等な Webhook 処理"""
    # delivery_id の重複チェック（ユニーク制約により保証）
    try:
        event = WebhookEvent.objects.create(
            delivery_id=delivery_id,
            event_type=event_type,
            source=source,
            payload=payload,
            status="RECEIVED",
        )
    except IntegrityError:
        # 既に処理済みの delivery_id → 409 を返してリトライ抑止
        return {"status": "already_processed", "delivery_id": delivery_id}, 409

    # 非同期タスクに委譲
    process_webhook_event.delay(event.pk)
    return {"status": "accepted", "delivery_id": delivery_id, "event_id": event.pk}, 202
```

---

## 7. 実装例

### 7.1 Webhook ビュー実装

```python
# webhooks/views.py
import json
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from webhooks.security import verify_webhook_signature
from webhooks.tasks import process_webhook_event

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class EntraWebhookView(View):
    """Azure Entra ID Webhook 受信エンドポイント"""

    def post(self, request):
        # 1. シグネチャ検証
        signature = request.headers.get("X-Webhook-Signature", "")
        timestamp = request.headers.get("X-Webhook-Timestamp", "")
        delivery_id = request.headers.get("X-Webhook-Delivery-ID", "")
        event_type = request.headers.get("X-Webhook-Event", "")

        try:
            verify_webhook_signature(
                payload_body=request.body,
                signature_header=signature,
                timestamp_header=timestamp,
                secret=settings.ENTRA_WEBHOOK_SECRET,
            )
        except SuspiciousOperation as e:
            logger.warning(f"Entra Webhook シグネチャ検証失敗: {e}")
            return JsonResponse({"error": "Signature verification failed"}, status=401)

        # 2. ペイロード解析
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # 3. 冪等処理
        response_data, status_code = process_webhook_idempotent(
            delivery_id=delivery_id,
            event_type=event_type,
            source="entra",
            payload=payload,
        )
        return JsonResponse(response_data, status=status_code)
```

### 7.2 Webhook イベント処理 Celery タスク

```python
# webhooks/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="webhook",
)
def process_webhook_event(self, event_pk: int):
    """Webhook イベントを処理する Celery タスク"""
    from webhooks.models import WebhookEvent

    event = WebhookEvent.objects.get(pk=event_pk)
    event.status = "PROCESSING"
    event.save(update_fields=["status"])

    try:
        handler = get_event_handler(event.event_type, event.source)
        handler(event.payload)

        event.status = "PROCESSED"
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])

    except Exception as exc:
        logger.error(
            f"Webhook イベント処理失敗: event_pk={event_pk}, "
            f"event_type={event.event_type}, error={exc}"
        )
        event.error_message = str(exc)
        event.save(update_fields=["error_message"])

        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            event.status = "FAILED"
            event.save(update_fields=["status"])
            _notify_admin_webhook_failure(event)


def get_event_handler(event_type: str, source: str):
    """イベントタイプとソースに対応するハンドラーを返す"""
    handlers = {
        ("user.created", "entra"): handle_entra_user_created,
        ("user.updated", "entra"): handle_entra_user_updated,
        ("user.disabled", "entra"): handle_entra_user_disabled,
        ("user.created", "hengeone"): handle_hengeone_user_created,
        ("user.disabled", "hengeone"): handle_hengeone_user_disabled,
        ("user.role_assigned", "entra"): handle_entra_role_assigned,
        ("user.role_removed", "entra"): handle_entra_role_removed,
    }
    handler = handlers.get((event_type, source))
    if not handler:
        logger.info(f"未対応のイベントタイプ: {event_type} / {source}")
        return lambda payload: None  # ノーオペレーション
    return handler
```

### 7.3 イベントハンドラー実装例

```python
# webhooks/handlers/entra.py


def handle_entra_user_created(payload: dict):
    """EntraID ユーザー作成イベントの処理"""
    entra_data = payload.get("data", {}).get("user", {})
    entra_object_id = entra_data.get("id")

    if not entra_object_id:
        raise ValueError("entra_object_id が取得できません")

    user, created = find_or_create_user_from_entra(entra_data)

    if created:
        logger.info(f"JIT プロビジョニング: entra_object_id={entra_object_id}")
    else:
        # 既存ユーザーに entra_object_id を紐付け
        if not user.entra_object_id:
            user.entra_object_id = entra_object_id
            user.save(update_fields=["entra_object_id"])

    # グループ / ロール同期を非同期で実行
    from integrations.entra.tasks import sync_user_groups_from_entra
    sync_user_groups_from_entra.delay(user.pk)


def handle_entra_user_disabled(payload: dict):
    """EntraID ユーザー無効化イベントの処理"""
    entra_object_id = payload["data"]["user"]["id"]

    user = User.objects.filter(entra_object_id=entra_object_id).first()
    if not user:
        logger.warning(f"対応ユーザー未存在: entra_object_id={entra_object_id}")
        return

    user.is_active = False
    user.save(update_fields=["is_active"])

    # 他システムへも伝播（AD / HENGEONE）
    from integrations.ad.tasks import disable_user_in_ad
    from integrations.hengeone.tasks import deprovision_user_hengeone_task
    disable_user_in_ad.delay(user.pk)
    deprovision_user_hengeone_task.delay(user.pk)
```

### 7.4 URL 設定

```python
# webhooks/urls.py
from django.urls import path
from webhooks.views import EntraWebhookView, HengeOneWebhookView, GenericWebhookView

urlpatterns = [
    path("webhooks/entra/", EntraWebhookView.as_view(), name="webhook-entra"),
    path("webhooks/hengeone/", HengeOneWebhookView.as_view(), name="webhook-hengeone"),
    path("webhooks/generic/", GenericWebhookView.as_view(), name="webhook-generic"),
]
```

---

## 8. 監視・運用

### 8.1 Webhook 監視指標

| 指標 | 説明 | 警告閾値 | 緊急閾値 |
|------|------|---------|---------|
| 受信率 | 単位時間あたりの Webhook 受信数 | - | 異常急増 |
| 処理成功率 | PROCESSED / RECEIVED の割合 | < 95% | < 80% |
| 処理遅延 | 受信から処理完了までの時間 | > 5分 | > 15分 |
| 失敗件数 | FAILED ステータスの累計 | > 5件/時 | > 20件/時 |
| 重複受信率 | SKIPPED / RECEIVED の割合 | > 5% | > 20% |

### 8.2 管理 API

```
GET  /api/v1/admin/webhooks/events/          # イベント一覧
GET  /api/v1/admin/webhooks/events/{id}/     # イベント詳細
POST /api/v1/admin/webhooks/events/{id}/retry/  # 手動リトライ
GET  /api/v1/admin/webhooks/statistics/      # 統計情報
```

---

## 9. 関連文書

| 文書番号 | 文書名 |
|---------|-------|
| INT-OVR-001 | 外部システム連携概要 |
| INT-ENT-001 | EntraID 連携設計 |
| INT-HEN-001 | HENGEONE 連携設計 |
| SEC-001 | セキュリティ設計概要 |
| OPS-001 | 運用監視設計 |
