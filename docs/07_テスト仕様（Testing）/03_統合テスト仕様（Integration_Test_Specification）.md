# 統合テスト仕様（Integration Test Specification）

| 項目 | 内容 |
|------|------|
| 文書番号 | TST-INT-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | ZeroTrust-ID-Governance 開発チーム |
| ステータス | 承認済み |

---

## 1. 概要

統合テストは、API 層と DB 層の結合動作を検証します。単体テストが個々のコンポーネントをモック化して検証するのに対し、統合テストは **実際の PostgreSQL に接続した状態**で API エンドポイントの動作を検証します。

### 1.1 統合テストの位置づけ

```mermaid
graph LR
    A[HTTP リクエスト] --> B[FastAPI Router]
    B --> C[Service Layer]
    C --> D[SQLAlchemy ORM]
    D --> E[(PostgreSQL テスト DB)]
    E --> D
    D --> C
    C --> B
    B --> F[HTTP レスポンス]

    style E fill:#3498db,color:#fff,stroke:#2980b9
    note["統合テストの検証範囲: A→F 全体"]
```

### 1.2 統合テスト対象

| テスト領域 | 説明 | テストファイル |
|------------|------|----------------|
| ユーザー管理 API + DB | CRUD 全操作と DB 整合性 | `test_integration_users.py` |
| 認証フロー + DB | ログイン・トークン発行・検証 | `test_integration_auth.py` |
| RBAC + DB | ロール割り当て・権限チェック | `test_integration_rbac.py` |
| アクセス申請 + DB | 申請ワークフロー全体 | `test_integration_access_requests.py` |
| 監査ログ + DB | ログ記録・検索・集計 | `test_integration_audit_logs.py` |
| 外部コネクタ統合 | LDAP/Keycloak のモック統合 | `test_integration_connectors.py` |

---

## 2. テスト用 PostgreSQL セットアップ

### 2.1 Docker Compose による テスト DB 起動

```yaml
# docker-compose.test.yml
version: "3.9"
services:
  postgres-test:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpassword
      POSTGRES_DB: zerotrust_test
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data  # メモリ上に展開（高速化）
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U testuser -d zerotrust_test"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"
```

```bash
# テスト環境起動
docker-compose -f docker-compose.test.yml up -d

# 統合テスト実行
pytest tests/integration/ -v --tb=short

# テスト環境停止
docker-compose -f docker-compose.test.yml down
```

### 2.2 pytest fixtures によるテスト DB 管理

```python
# tests/integration/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.pool import NullPool
from app.models.base import Base
from app.core.config import settings

TEST_DATABASE_URL = (
    "postgresql+asyncpg://testuser:testpassword@localhost:5433/zerotrust_test"
)


@pytest.fixture(scope="session")
def event_loop_policy():
    """イベントループポリシーの設定"""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """テスト用エンジン（セッションスコープ）"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,  # 接続プールを無効化
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """各テスト用 DB セッション（テスト後ロールバック）"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()  # テスト後に全変更をロールバック


@pytest_asyncio.fixture
async def integration_client(db_session):
    """DB セッションをオーバーライドした統合テストクライアント"""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.dependencies import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

### 2.3 テストデータファクトリー

```python
# tests/factories.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.models.user import User
from app.models.role import Role
from app.core.security import get_password_hash


class RoleFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Role
        sqlalchemy_session_persistence = "commit"

    name = factory.Sequence(lambda n: f"role_{n}")
    description = factory.Faker("sentence", nb_words=5, locale="ja_JP")
    permissions = ["users:read"]


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    full_name = factory.Faker("name", locale="ja_JP")
    hashed_password = factory.LazyFunction(
        lambda: get_password_hash("TestPass123!")
    )
    is_active = True
    is_superuser = False
```

---

## 3. FastAPI 統合テスト

### 3.1 TestClient を使用した統合テスト

```python
# tests/integration/test_integration_users.py
import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestUsersIntegration:
    """ユーザー管理 API + DB 統合テスト"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_user_when_valid_data_then_persisted_to_db(
        self, integration_client: AsyncClient, db_session
    ):
        """ユーザー作成後に DB に正しく保存されることを確認"""
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "SecurePass123!",
        }
        response = await integration_client.post(
            "/api/v1/users",
            json=payload,
            headers={"Authorization": "Bearer <admin_token>"}
        )

        assert response.status_code == 201
        user_id = response.json()["id"]

        # DB に実際に保存されているか確認
        from sqlalchemy import select
        from app.models.user import User
        result = await db_session.execute(
            select(User).where(User.id == user_id)
        )
        db_user = result.scalar_one_or_none()

        assert db_user is not None
        assert db_user.email == payload["email"]
        assert db_user.username == payload["username"]
        assert db_user.is_active is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_users_when_multiple_exist_then_returns_all(
        self, integration_client: AsyncClient, db_session
    ):
        """複数ユーザーが存在する場合に全件返却されることを確認"""
        from tests.factories import UserFactory
        UserFactory._meta.sqlalchemy_session = db_session

        users = UserFactory.create_batch(5)

        response = await integration_client.get("/api/v1/users")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 5

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_user_when_exists_then_removed_from_db(
        self, integration_client: AsyncClient, db_session
    ):
        """ユーザー削除後に DB から除去されることを確認"""
        from tests.factories import UserFactory
        UserFactory._meta.sqlalchemy_session = db_session
        user = UserFactory.create()

        response = await integration_client.delete(
            f"/api/v1/users/{user.id}",
            headers={"Authorization": "Bearer <admin_token>"}
        )
        assert response.status_code == 204

        # DB から実際に削除されているか確認
        from sqlalchemy import select
        from app.models.user import User
        result = await db_session.execute(
            select(User).where(User.id == user.id)
        )
        assert result.scalar_one_or_none() is None
```

---

## 4. 認証フロー統合テスト

### 4.1 ログイン〜トークン発行フロー

```python
# tests/integration/test_integration_auth.py
import pytest
from httpx import AsyncClient
from jose import jwt
from app.core.config import settings


class TestAuthIntegration:
    """認証フロー統合テスト"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_login_when_valid_credentials_then_returns_jwt_token(
        self, integration_client: AsyncClient, db_session
    ):
        """有効な資格情報でログインすると JWT トークンが返ることを確認"""
        from tests.factories import UserFactory
        from app.core.security import get_password_hash
        UserFactory._meta.sqlalchemy_session = db_session

        user = UserFactory.create(
            hashed_password=get_password_hash("ValidPass123!")
        )

        response = await integration_client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "ValidPass123!",
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # JWT の内容を検証
        payload = jwt.decode(
            data["access_token"],
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        assert payload["sub"] == user.email

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_login_when_invalid_password_then_returns_401(
        self, integration_client: AsyncClient, db_session
    ):
        """無効なパスワードで 401 が返ることを確認"""
        from tests.factories import UserFactory
        UserFactory._meta.sqlalchemy_session = db_session
        user = UserFactory.create()

        response = await integration_client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "WrongPassword!",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_refresh_token_when_valid_then_returns_new_access_token(
        self, integration_client: AsyncClient, db_session
    ):
        """リフレッシュトークンで新しいアクセストークンが取得できることを確認"""
        # ログインしてトークンを取得
        login_response = await integration_client.post(
            "/api/v1/auth/login", json={...}
        )
        refresh_token = login_response.json()["refresh_token"]

        # リフレッシュ実行
        refresh_response = await integration_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_protected_endpoint_when_token_expired_then_returns_401(
        self, integration_client: AsyncClient
    ):
        """期限切れトークンで保護エンドポイントにアクセスすると 401 が返ることを確認"""
        from app.core.security import create_access_token
        from datetime import timedelta

        expired_token = create_access_token(
            data={"sub": "test@example.com"},
            expires_delta=timedelta(seconds=-1)  # 既に期限切れ
        )

        response = await integration_client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
```

---

## 5. RBAC 統合テスト

### 5.1 ロールベースアクセス制御の統合検証

```python
# tests/integration/test_integration_rbac.py
import pytest
from httpx import AsyncClient


class TestRBACIntegration:
    """RBAC 統合テスト（ロール + DB + API の結合検証）"""

    ROLE_PERMISSION_MATRIX = [
        # (role, endpoint, method, expected_status)
        ("viewer", "/api/v1/users", "GET", 200),
        ("viewer", "/api/v1/users", "POST", 403),
        ("viewer", "/api/v1/users/1", "DELETE", 403),
        ("approver", "/api/v1/access-requests/1/approve", "POST", 200),
        ("approver", "/api/v1/users", "POST", 403),
        ("admin", "/api/v1/users", "POST", 201),
        ("admin", "/api/v1/users/1", "DELETE", 204),
        ("admin", "/api/v1/roles", "POST", 201),
    ]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.parametrize("role,endpoint,method,expected", ROLE_PERMISSION_MATRIX)
    async def test_rbac_when_role_accesses_endpoint_then_correct_status(
        self,
        integration_client: AsyncClient,
        db_session,
        role: str,
        endpoint: str,
        method: str,
        expected: int
    ):
        """各ロールが各エンドポイントに正しいアクセス制御を受けることを確認"""
        from tests.factories import UserFactory, RoleFactory
        UserFactory._meta.sqlalchemy_session = db_session
        RoleFactory._meta.sqlalchemy_session = db_session

        role_obj = RoleFactory.create(name=role)
        user = UserFactory.create(roles=[role_obj])
        token = self._generate_token_for_user(user)

        if method == "GET":
            response = await integration_client.get(
                endpoint, headers={"Authorization": f"Bearer {token}"}
            )
        elif method == "POST":
            response = await integration_client.post(
                endpoint,
                json={},
                headers={"Authorization": f"Bearer {token}"}
            )
        elif method == "DELETE":
            response = await integration_client.delete(
                endpoint, headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == expected, (
            f"Role '{role}' on {method} {endpoint}: "
            f"expected {expected}, got {response.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_role_assignment_when_admin_assigns_role_then_user_gains_permission(
        self, integration_client: AsyncClient, db_session
    ):
        """管理者がユーザーにロールを付与するとアクセス権が変化することを確認"""
        from tests.factories import UserFactory
        UserFactory._meta.sqlalchemy_session = db_session

        # viewer ロールのユーザーを作成
        user = UserFactory.create()
        viewer_token = self._generate_token_for_user(user)

        # 最初は管理操作が拒否されることを確認
        response = await integration_client.post(
            "/api/v1/users",
            json={...},
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert response.status_code == 403

        # 管理者が admin ロールを付与
        admin_token = self._get_admin_token()
        await integration_client.post(
            f"/api/v1/users/{user.id}/roles",
            json={"role_name": "admin"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # ロール付与後は管理操作が許可されることを確認
        new_token = self._generate_token_for_user(user)  # トークン再発行
        response = await integration_client.post(
            "/api/v1/users",
            json={...},
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert response.status_code == 201
```

---

## 6. 外部システムコネクタのモックストラテジー

### 6.1 コネクタモックの方針

統合テストでは DB は実接続しますが、外部システム（LDAP / Keycloak / Slack）はモック化します。

```mermaid
graph LR
    API[FastAPI API] --> DB[(PostgreSQL)]
    API --> LDAP_MOCK[LDAP Mock]
    API --> KC_MOCK[Keycloak Mock]
    API --> SLACK_MOCK[Slack Mock]

    style DB fill:#27ae60,color:#fff
    style LDAP_MOCK fill:#e74c3c,color:#fff
    style KC_MOCK fill:#e74c3c,color:#fff
    style SLACK_MOCK fill:#e74c3c,color:#fff
```

### 6.2 Keycloak コネクタモック

```python
# tests/integration/conftest.py（コネクタモック）
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def mock_keycloak_connector():
    """Keycloak コネクタを自動モック（全統合テストに適用）"""
    with patch(
        "app.connectors.keycloak_connector.KeycloakConnector"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.get_user = AsyncMock(return_value={
            "id": "keycloak-user-uuid",
            "username": "testuser",
            "enabled": True,
        })
        instance.create_user = AsyncMock(return_value={
            "id": "new-keycloak-uuid"
        })
        instance.delete_user = AsyncMock(return_value=True)
        instance.assign_role = AsyncMock(return_value=True)
        instance.get_token = AsyncMock(return_value={
            "access_token": "keycloak-token",
            "expires_in": 300,
        })
        yield instance


@pytest.fixture(autouse=True)
def mock_ldap_connector():
    """LDAP コネクタを自動モック"""
    with patch(
        "app.connectors.ldap_connector.LDAPConnector"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.search_user = AsyncMock(return_value=[
            {"dn": "uid=testuser,ou=users,dc=example,dc=com", "cn": "Test User"}
        ])
        instance.authenticate = AsyncMock(return_value=True)
        instance.sync_groups = AsyncMock(return_value={"synced": 10})
        yield instance


@pytest.fixture(autouse=True)
def mock_slack_connector():
    """Slack コネクタを自動モック"""
    with patch(
        "app.connectors.slack_connector.SlackConnector"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.send_notification = AsyncMock(return_value={"ok": True})
        instance.send_approval_request = AsyncMock(return_value={"ok": True})
        yield instance
```

### 6.3 アクセス申請ワークフロー統合テスト

```python
# tests/integration/test_integration_access_requests.py
class TestAccessRequestWorkflowIntegration:
    """アクセス申請ワークフロー全体の統合テスト"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_access_request_full_workflow(
        self, integration_client: AsyncClient, db_session,
        mock_slack_connector
    ):
        """申請 → 承認 → 権限付与の完全ワークフローを検証"""

        # Step 1: ユーザーがアクセス申請を作成
        create_response = await integration_client.post(
            "/api/v1/access-requests",
            json={
                "resource": "production-database",
                "access_type": "read",
                "reason": "データ分析作業のため",
                "duration_days": 7,
            },
            headers={"Authorization": "Bearer <user_token>"}
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["id"]

        # Slack 通知が送信されたか確認
        mock_slack_connector.send_approval_request.assert_called_once()

        # Step 2: 申請が PENDING 状態であることを確認
        get_response = await integration_client.get(
            f"/api/v1/access-requests/{request_id}"
        )
        assert get_response.json()["status"] == "pending"

        # Step 3: 承認者が申請を承認
        approve_response = await integration_client.post(
            f"/api/v1/access-requests/{request_id}/approve",
            json={"comment": "承認します"},
            headers={"Authorization": "Bearer <approver_token>"}
        )
        assert approve_response.status_code == 200

        # Step 4: 申請が APPROVED 状態に更新されたことを DB で確認
        from sqlalchemy import select
        from app.models.access_request import AccessRequest
        result = await db_session.execute(
            select(AccessRequest).where(AccessRequest.id == request_id)
        )
        access_request = result.scalar_one()
        assert access_request.status == "approved"
        assert access_request.approved_by is not None

        # Step 5: 承認通知が送信されたか確認
        assert mock_slack_connector.send_notification.call_count >= 1
```

### 6.4 監査ログ記録統合テスト

```python
class TestAuditLogIntegration:
    """監査ログ自動記録の統合テスト"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_action_when_creates_user_then_audit_log_recorded(
        self, integration_client: AsyncClient, db_session
    ):
        """ユーザー作成操作が監査ログに記録されることを確認"""
        response = await integration_client.post(
            "/api/v1/users",
            json={"username": "audit_test_user", "email": "audit@example.com", ...},
            headers={"Authorization": "Bearer <admin_token>"}
        )
        assert response.status_code == 201
        user_id = response.json()["id"]

        # 監査ログが記録されているか確認
        from sqlalchemy import select
        from app.models.audit_log import AuditLog
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "user",
                AuditLog.resource_id == str(user_id),
                AuditLog.action == "create",
            )
        )
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.actor_id is not None
        assert audit_log.timestamp is not None
        assert audit_log.ip_address is not None
```

---

## 7. 統合テスト実行コマンド

```bash
# 統合テスト DB 起動
docker-compose -f docker-compose.test.yml up -d

# 全統合テスト実行
pytest tests/integration/ -v -m integration

# 特定カテゴリの統合テスト
pytest tests/integration/test_integration_auth.py -v
pytest tests/integration/test_integration_rbac.py -v

# 統合テストのみ（単体テストを除外）
pytest tests/integration/ -v --ignore=tests/unit/

# カバレッジ付き実行
pytest tests/integration/ --cov=app --cov-report=term-missing

# テスト DB クリーンアップ
docker-compose -f docker-compose.test.yml down -v
```

---

*最終更新: 2026-03-25 | 文書番号: TST-INT-001 | バージョン: 1.0.0*
