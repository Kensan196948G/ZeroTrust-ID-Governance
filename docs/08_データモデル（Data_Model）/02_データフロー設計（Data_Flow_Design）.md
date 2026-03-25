# データフロー設計（Data Flow Design）

| 項目 | 内容 |
|------|------|
| 文書番号 | DM-FLOW-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | ZeroTrust-ID-Governance 開発チーム |
| ステータス | 承認済み |

---

## 目次

1. [概要](#概要)
2. [システム全体データフロー](#システム全体データフロー)
3. [ユーザー作成フロー](#ユーザー作成フロー)
4. [アクセス申請フロー](#アクセス申請フロー)
5. [監査ログ生成フロー](#監査ログ生成フロー)
6. [データ変換・マッピング仕様](#データ変換マッピング仕様)

---

## 概要

本文書は ZeroTrust-ID-Governance システムにおけるデータの流れを定義する。
データはAPI層・DB層・非同期タスク層・外部システム連携層を通じて処理される。

### データフローの設計原則

| 原則 | 内容 |
|------|------|
| 単一責任 | 各コンポーネントは明確なデータ処理責務を持つ |
| 不変性 | 監査ログは追記専用（変更・削除不可） |
| 非同期処理 | 外部システム連携は Celery による非同期処理で実施 |
| トレーサビリティ | 全操作は `request_id` で追跡可能 |
| ゼロトラスト | 全リクエストは認証・認可を経由する |

---

## システム全体データフロー

```mermaid
flowchart TB
    subgraph Client["クライアント層"]
        WEB[Webブラウザ]
        API_CLIENT[APIクライアント / CLI]
    end

    subgraph API["API層（FastAPI）"]
        AUTH[認証ミドルウェア\nJWT検証]
        ROUTER[APIルーター]
        VALIDATOR[リクエストバリデーター\nPydantic]
        SERVICE[サービス層\nビジネスロジック]
    end

    subgraph DB["データベース層（PostgreSQL 16）"]
        USERS_TBL[(users)]
        DEPT_TBL[(departments)]
        ROLES_TBL[(roles)]
        USER_ROLES_TBL[(user_roles)]
        REQ_TBL[(access_requests)]
        AUDIT_TBL[(audit_logs)]
    end

    subgraph ASYNC["非同期タスク層（Celery + Redis）"]
        CELERY[Celeryワーカー]
        REDIS[(Redis\nメッセージキュー)]
    end

    subgraph EXT["外部システム"]
        LDAP[Active Directory\n/ LDAP]
        SLACK[Slack\n通知]
        EMAIL[メール\n通知]
        SIEM[SIEM\n監査ログ転送]
    end

    WEB -->|HTTPS| AUTH
    API_CLIENT -->|HTTPS| AUTH
    AUTH -->|JWT検証済みリクエスト| ROUTER
    ROUTER --> VALIDATOR
    VALIDATOR -->|バリデーション済みデータ| SERVICE
    SERVICE -->|SQLAlchemy ORM| USERS_TBL
    SERVICE -->|SQLAlchemy ORM| DEPT_TBL
    SERVICE -->|SQLAlchemy ORM| ROLES_TBL
    SERVICE -->|SQLAlchemy ORM| USER_ROLES_TBL
    SERVICE -->|SQLAlchemy ORM| REQ_TBL
    SERVICE -->|監査ログ自動記録| AUDIT_TBL
    SERVICE -->|タスクキュー| REDIS
    REDIS --> CELERY
    CELERY -->|プロビジョニング| LDAP
    CELERY -->|通知| SLACK
    CELERY -->|通知| EMAIL
    CELERY -->|ログ転送| SIEM
```

---

## ユーザー作成フロー

### フロー概要

```mermaid
flowchart TD
    START([ユーザー作成リクエスト]) --> RECV[APIエンドポイント受信\nPOST /api/v1/users]
    RECV --> AUTH_CHK{JWT認証\n検証}
    AUTH_CHK -->|認証失敗| ERR401[401 Unauthorized\nレスポンス]
    AUTH_CHK -->|認証成功| PERM_CHK{権限チェック\nADMINロール確認}
    PERM_CHK -->|権限なし| ERR403[403 Forbidden\nレスポンス]
    PERM_CHK -->|権限あり| VALIDATE{リクエスト\nバリデーション}
    VALIDATE -->|バリデーション失敗| ERR422[422 Validation Error\nレスポンス]
    VALIDATE -->|バリデーション成功| DUPL_CHK{重複チェック\nemail / username}
    DUPL_CHK -->|重複あり| ERR409[409 Conflict\nレスポンス]
    DUPL_CHK -->|重複なし| TX_START[DBトランザクション開始]
    TX_START --> HASH_PWD[パスワードハッシュ化\nbcrypt rounds=12]
    HASH_PWD --> INSERT_USER[users テーブル\nINSERT]
    INSERT_USER --> INSERT_AUDIT[audit_logs テーブル\nINSERT\naction=CREATE resource=users]
    INSERT_AUDIT --> TX_COMMIT[トランザクション\nCOMMIT]
    TX_COMMIT --> ENQUEUE[Celery タスクキュー\nへエンキュー]
    ENQUEUE --> RESP[201 Created\nレスポンス返却]
    ENQUEUE --> ASYNC_PROC[非同期処理]

    subgraph ASYNC_PROC["非同期処理（Celery Worker）"]
        TASK_AD[ADプロビジョニング\ntask_provision_ad]
        TASK_MAIL[ウェルカムメール送信\ntask_send_welcome_email]
        TASK_SLACK[Slack通知\ntask_notify_slack]
    end
```

### データ変換（リクエスト → DB）

| フィールド | リクエスト（JSON） | DBカラム | 変換処理 |
|---------|----------------|---------|---------|
| `username` | `"john_doe"` | `username` | 小文字化・前後トリム |
| `email` | `"John@Example.com"` | `email` | 小文字化 |
| `full_name` | `"John Doe"` | `full_name` | 前後トリム |
| `department_id` | `"uuid-string"` | `department_id` | UUID型変換・存在確認 |
| `password` | `"raw_password"` | `password_hash` | bcrypt ハッシュ化（平文は保存しない） |
| - | - | `id` | UUID v4 自動生成 |
| - | - | `is_active` | `TRUE`（デフォルト） |
| - | - | `is_locked` | `FALSE`（デフォルト） |
| - | - | `created_at` | `NOW()` UTC |
| - | - | `updated_at` | `NOW()` UTC |

### SQLAlchemy 実装例

```python
from app.models import User
from app.schemas import UserCreateRequest
from app.core.security import hash_password
from app.tasks import provision_ad, send_welcome_email

async def create_user(
    db: AsyncSession,
    request: UserCreateRequest,
    current_user: User
) -> User:
    # 重複チェック
    existing = await db.execute(
        select(User).where(
            (User.email == request.email.lower()) |
            (User.username == request.username.lower())
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("email または username が既に存在します")

    # ユーザー生成
    user = User(
        username=request.username.lower().strip(),
        email=request.email.lower(),
        full_name=request.full_name.strip(),
        department_id=request.department_id,
        password_hash=hash_password(request.password),
    )
    db.add(user)

    # 監査ログ記録
    audit_log = AuditLog(
        user_id=current_user.id,
        action="CREATE",
        resource="users",
        resource_id=user.id,
        new_value=user.to_dict(),
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    # 非同期タスクをキュー
    provision_ad.delay(str(user.id))
    send_welcome_email.delay(str(user.id))

    return user
```

---

## アクセス申請フロー

### フロー概要

```mermaid
flowchart TD
    START([申請者がアクセス申請]) --> REQ[POST /api/v1/access-requests\n申請情報送信]
    REQ --> VALIDATE{バリデーション\n申請理由・ロールID確認}
    VALIDATE -->|NG| ERR[エラーレスポンス]
    VALIDATE -->|OK| DUPL_CHK{同一ロールの\n未処理申請確認}
    DUPL_CHK -->|重複申請| ERR409[409 Conflict]
    DUPL_CHK -->|問題なし| INSERT_REQ[access_requests\nINSERT\nstatus=pending]
    INSERT_REQ --> INSERT_AUDIT1[audit_logs\nINSERT\naction=CREATE\nresource=access_requests]
    INSERT_AUDIT1 --> NOTIFY_APPROVER[承認者への\nメール・Slack通知\n（Celeryタスク）]

    NOTIFY_APPROVER --> WAIT_REVIEW{承認者レビュー待ち}

    WAIT_REVIEW -->|承認| APPROVE[PATCH /api/v1/access-requests/:id\nstatus=approved]
    WAIT_REVIEW -->|却下| REJECT[PATCH /api/v1/access-requests/:id\nstatus=rejected]
    WAIT_REVIEW -->|期限切れ| EXPIRE[バッチ処理で\nstatus=cancelled]

    APPROVE --> UPDATE_REQ_A[access_requests UPDATE\nstatus=approved\napprover_id\nreviewed_at]
    UPDATE_REQ_A --> INSERT_AUDIT2[audit_logs\nINSERT\naction=APPROVE]
    INSERT_AUDIT2 --> PROVISION[Celery タスク\n非同期プロビジョニング]

    PROVISION --> INSERT_USER_ROLE[user_roles\nINSERT\ngranted_by=承認者ID]
    INSERT_USER_ROLE --> PROV_AD[ADプロビジョニング\n外部システム連携]
    PROV_AD --> UPDATE_REQ_P[access_requests UPDATE\nstatus=provisioned\nprovisioned_at]
    UPDATE_REQ_P --> INSERT_AUDIT3[audit_logs\nINSERT\naction=PROVISION]
    INSERT_AUDIT3 --> NOTIFY_REQUESTER_OK[申請者へ\n完了通知]

    REJECT --> UPDATE_REQ_R[access_requests UPDATE\nstatus=rejected\nrejection_reason\nreviewed_at]
    UPDATE_REQ_R --> INSERT_AUDIT_R[audit_logs\nINSERT\naction=REJECT]
    INSERT_AUDIT_R --> NOTIFY_REQUESTER_NG[申請者へ\n却下通知]
```

### ステータス遷移詳細

| 現ステータス | トリガー | 次ステータス | 処理内容 |
|-----------|---------|------------|---------|
| `pending` | 承認者が承認 | `approved` | `approver_id`, `reviewed_at` セット |
| `pending` | 承認者が却下 | `rejected` | `rejection_reason`, `reviewed_at` セット |
| `pending` | 申請者がキャンセル | `cancelled` | `updated_at` セット |
| `pending` | バッチ処理（期限切れ） | `cancelled` | `expires_at` 超過時に自動更新 |
| `approved` | Celeryプロビジョニング完了 | `provisioned` | `provisioned_at` セット・`user_roles` 挿入 |

---

## 監査ログ生成フロー

### フロー概要

```mermaid
flowchart LR
    subgraph API_LAYER["API層"]
        REQ[HTTPリクエスト受信]
        MIDDLEWARE[監査ミドルウェア\n自動記録]
        HANDLER[APIハンドラー\n処理実行]
        RESP[HTTPレスポンス返却]
    end

    subgraph DB_LAYER["DB層"]
        AUDIT_TBL[(audit_logs)]
        RESOURCE_TBL[(対象テーブル)]
    end

    subgraph EXPORT["外部エクスポート"]
        SIEM[SIEM / Splunk]
        S3[S3 / オブジェクトストレージ]
    end

    REQ --> MIDDLEWARE
    MIDDLEWARE -->|request_id 生成| HANDLER
    HANDLER -->|DB操作| RESOURCE_TBL
    HANDLER -->|完了後コールバック| MIDDLEWARE
    MIDDLEWARE -->|監査ログ挿入| AUDIT_TBL
    MIDDLEWARE --> RESP
    AUDIT_TBL -->|Celery定期タスク| SIEM
    AUDIT_TBL -->|月次バッチ| S3
```

### 監査ログ自動記録の仕組み

```python
# FastAPI ミドルウェアによる自動記録
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4()
        request.state.request_id = request_id

        response = await call_next(request)

        # 書き込み系操作のみ監査ログを記録
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            await self._record_audit(
                request=request,
                response=response,
                request_id=request_id,
            )

        return response

    async def _record_audit(self, request, response, request_id):
        user_id = getattr(request.state, "user_id", None)
        audit_log = AuditLog(
            user_id=user_id,
            action=self._resolve_action(request.method),
            resource=self._resolve_resource(request.url.path),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            request_id=request_id,
            status_code=response.status_code,
        )
        await db.execute(insert(AuditLog).values(**audit_log.dict()))
```

### 記録される操作一覧

| 操作 | `action` 値 | `resource` 値 | 記録タイミング |
|-----|-----------|-------------|------------|
| ユーザー作成 | `CREATE` | `users` | コミット後 |
| ユーザー更新 | `UPDATE` | `users` | コミット後 |
| ユーザー削除 | `DELETE` | `users` | コミット後 |
| ロール付与 | `GRANT_ROLE` | `user_roles` | コミット後 |
| ロール剥奪 | `REVOKE_ROLE` | `user_roles` | コミット後 |
| アクセス申請 | `CREATE` | `access_requests` | コミット後 |
| 申請承認 | `APPROVE` | `access_requests` | コミット後 |
| 申請却下 | `REJECT` | `access_requests` | コミット後 |
| プロビジョニング | `PROVISION` | `access_requests` | Celery完了後 |
| ログイン成功 | `LOGIN_SUCCESS` | `auth` | 認証成功時 |
| ログイン失敗 | `LOGIN_FAILURE` | `auth` | 認証失敗時 |
| ログアウト | `LOGOUT` | `auth` | ログアウト時 |

---

## データ変換・マッピング仕様

### APIレスポンス → DBエンティティ 変換規則

```mermaid
flowchart LR
    subgraph INPUT["入力（リクエストJSON）"]
        J1["{ username, email,\nfull_name, password,\ndepartment_id }"]
    end

    subgraph TRANSFORM["変換処理"]
        T1[文字列正規化\n小文字化・トリム]
        T2[バリデーション\nPydantic スキーマ]
        T3[セキュリティ変換\nパスワードハッシュ化]
        T4[UUID生成\nauto-assign]
        T5[タイムスタンプ\nUTC NOW()]
    end

    subgraph OUTPUT["出力（DBレコード）"]
        D1["{ id: UUID,\nusername: str,\nemail: str,\nfull_name: str,\ndepartment_id: UUID,\npassword_hash: str,\nis_active: bool,\nis_locked: bool,\ncreated_at: timestamptz,\nupdated_at: timestamptz }"]
    end

    J1 --> T1 --> T2 --> T3 --> T4 --> T5 --> D1
```

### 型マッピング表

| Python型 | SQLAlchemy型 | PostgreSQL型 | 備考 |
|---------|------------|------------|------|
| `uuid.UUID` | `UUID(as_uuid=True)` | `UUID` | ネイティブUUID型 |
| `str` | `String(N)` | `VARCHAR(N)` | N = 最大文字数 |
| `str` | `Text` | `TEXT` | 長文テキスト |
| `bool` | `Boolean` | `BOOLEAN` | - |
| `int` | `Integer` | `INTEGER` | - |
| `datetime` | `DateTime(timezone=True)` | `TIMESTAMPTZ` | 常にUTC |
| `dict` | `JSONB` | `JSONB` | GINインデックス対応 |
| `Enum` | `Enum(name=...)` | `ENUM型` | PostgreSQL ENUM |
| `IPv4Address` | `INET` | `INET` | IPv4/IPv6対応 |

### レスポンス変換（DB → API）

```python
# Pydantic スキーマによるシリアライズ
from pydantic import BaseModel, field_serializer
from datetime import datetime
from uuid import UUID

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    department_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("id", "department_id")
    def serialize_uuid(self, v: UUID | None) -> str | None:
        return str(v) if v else None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, v: datetime) -> str:
        # ISO 8601 形式・UTC明示
        return v.isoformat()
```

### 機密データのマスキング

| フィールド | API レスポンスでの扱い | 監査ログでの扱い |
|---------|-------------------|--------------|
| `password_hash` | **除外**（返却しない） | **除外** |
| `email` | 完全表示（認証済みのみ） | 完全表示 |
| `ip_address` | 除外 | 完全記録 |
| `old_value` | 除外 | 完全記録（変更前） |
| `new_value` | 除外 | 完全記録（変更後） |

---

## 改訂履歴

| バージョン | 日付 | 変更内容 | 変更者 |
|----------|------|---------|-------|
| 1.0.0 | 2026-03-25 | 初版作成 | 開発チーム |
