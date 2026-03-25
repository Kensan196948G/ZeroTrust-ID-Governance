# 単体テスト仕様（Unit Test Specification）

| 項目 | 内容 |
|------|------|
| 文書番号 | TST-UNIT-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | ZeroTrust-ID-Governance 開発チーム |
| ステータス | 承認済み |

---

## 1. 概要

単体テストは ZeroTrust-ID-Governance バックエンドの各モジュールを独立して検証します。pytest および pytest-asyncio を使用し、外部依存（DB・外部 API）はすべてモック化することで高速かつ安定したテスト実行を実現します。

### 1.1 現在のテスト実績

| 指標 | 実績値 |
|------|--------|
| 総テスト数 | **273 tests** |
| パス数 | **273 / 273（100%）** |
| コードカバレッジ | **97%** |
| 平均実行時間 | ~45秒 |

---

## 2. 対象ファイル一覧

### 2.1 テスト対象モジュール

| モジュール | パス | テストファイル | カバレッジ |
|------------|------|----------------|------------|
| **モデル層** | `app/models/` | `tests/unit/test_models/` | 98% |
| `UserModel` | `app/models/user.py` | `test_user_model.py` | 99% |
| `RoleModel` | `app/models/role.py` | `test_role_model.py` | 97% |
| `AccessRequestModel` | `app/models/access_request.py` | `test_access_request_model.py` | 98% |
| `AuditLogModel` | `app/models/audit_log.py` | `test_audit_log_model.py` | 96% |
| **API 層** | `app/api/` | `tests/unit/test_api/` | 97% |
| `users` ルーター | `app/api/v1/users.py` | `test_users_api.py` | 97% |
| `auth` ルーター | `app/api/v1/auth.py` | `test_auth_api.py` | 98% |
| `roles` ルーター | `app/api/v1/roles.py` | `test_roles_api.py` | 96% |
| `access_requests` ルーター | `app/api/v1/access_requests.py` | `test_access_requests_api.py` | 97% |
| `audit_logs` ルーター | `app/api/v1/audit_logs.py` | `test_audit_logs_api.py` | 95% |
| **コアロジック** | `app/core/` | `tests/unit/test_core/` | 98% |
| `security` | `app/core/security.py` | `test_security.py` | 99% |
| `dependencies` | `app/core/dependencies.py` | `test_dependencies.py` | 97% |
| `config` | `app/core/config.py` | `test_config.py` | 95% |
| **エンジン層** | `app/engine/` | `tests/unit/test_engine/` | 96% |
| `rbac_engine` | `app/engine/rbac_engine.py` | `test_rbac_engine.py` | 97% |
| `policy_engine` | `app/engine/policy_engine.py` | `test_policy_engine.py` | 96% |
| `audit_engine` | `app/engine/audit_engine.py` | `test_audit_engine.py` | 95% |
| **コネクタ層** | `app/connectors/` | `tests/unit/test_connectors/` | 94% |
| `ldap_connector` | `app/connectors/ldap_connector.py` | `test_ldap_connector.py` | 95% |
| `keycloak_connector` | `app/connectors/keycloak_connector.py` | `test_keycloak_connector.py` | 94% |
| `slack_connector` | `app/connectors/slack_connector.py` | `test_slack_connector.py` | 93% |

---

## 3. pytest + pytest-asyncio セットアップ

### 3.1 依存パッケージ

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--cov=app",
    "--cov-report=html:htmlcov",
    "--cov-report=term-missing",
    "--cov-fail-under=95",
    "-v",
    "--strict-markers",
]
markers = [
    "unit: 単体テスト",
    "integration: 統合テスト",
    "e2e: E2Eテスト",
    "slow: 実行時間が長いテスト",
    "security: セキュリティテスト",
]

[tool.coverage.run]
source = ["app"]
omit = [
    "app/migrations/*",
    "app/alembic/*",
    "*/conftest.py",
]
```

```txt
# requirements-dev.txt
pytest==8.1.1
pytest-asyncio==0.23.6
pytest-cov==5.0.0
pytest-mock==3.14.0
httpx==0.27.0
factory-boy==3.3.0
faker==24.11.0
```

### 3.2 conftest.py 基本構成

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.core.dependencies import get_db, get_current_user


@pytest.fixture
def mock_db_session():
    """非同期 DB セッションのモック"""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_current_user():
    """認証済みユーザーのモック"""
    return MagicMock(
        id=1,
        email="test@example.com",
        username="testuser",
        is_active=True,
        is_superuser=False,
        roles=["viewer"],
    )


@pytest.fixture
def mock_superuser():
    """スーパーユーザーのモック"""
    return MagicMock(
        id=999,
        email="admin@example.com",
        username="admin",
        is_active=True,
        is_superuser=True,
        roles=["admin", "viewer", "approver"],
    )
```

---

## 4. テストクラス設計（TestXxx パターン）

### 4.1 テストクラス構造

```python
# tests/unit/test_api/test_users_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from app.main import app
from app.core.dependencies import get_db, get_current_user


class TestUsersGetList:
    """ユーザー一覧取得エンドポイントのテスト群"""

    @pytest.mark.asyncio
    async def test_get_users_when_authenticated_then_returns_list(
        self, async_client, mock_db_session, mock_current_user
    ):
        """認証済みユーザーが一覧を取得できることを確認"""
        ...

    @pytest.mark.asyncio
    async def test_get_users_when_unauthenticated_then_returns_401(
        self, async_client
    ):
        """未認証ユーザーが 401 を受け取ることを確認"""
        ...

    @pytest.mark.asyncio
    async def test_get_users_when_page_param_given_then_applies_pagination(
        self, async_client, mock_db_session, mock_current_user
    ):
        """ページネーションパラメータが正しく適用されることを確認"""
        ...


class TestUsersCreate:
    """ユーザー作成エンドポイントのテスト群"""

    @pytest.mark.asyncio
    async def test_create_user_when_valid_data_then_returns_201(
        self, async_client, mock_db_session, mock_superuser
    ):
        """有効なデータでユーザーが作成されることを確認"""
        ...

    @pytest.mark.asyncio
    async def test_create_user_when_duplicate_email_then_returns_409(
        self, async_client, mock_db_session, mock_superuser
    ):
        """重複メールアドレスで 409 が返ることを確認"""
        ...

    @pytest.mark.asyncio
    async def test_create_user_when_insufficient_permission_then_returns_403(
        self, async_client, mock_db_session, mock_current_user
    ):
        """権限不足で 403 が返ることを確認"""
        ...


class TestUsersUpdate:
    """ユーザー更新エンドポイントのテスト群"""
    ...


class TestUsersDelete:
    """ユーザー削除エンドポイントのテスト群"""
    ...
```

### 4.2 テストクラス命名規則

| パターン | 説明 | 例 |
|----------|------|----|
| `TestXxxGetList` | 一覧取得テスト群 | `TestUsersGetList` |
| `TestXxxGetById` | 単件取得テスト群 | `TestUsersGetById` |
| `TestXxxCreate` | 作成テスト群 | `TestUsersCreate` |
| `TestXxxUpdate` | 更新テスト群 | `TestUsersUpdate` |
| `TestXxxDelete` | 削除テスト群 | `TestUsersDelete` |
| `TestXxxAuth` | 認証テスト群 | `TestJWTAuth` |
| `TestXxxEngine` | エンジンロジックテスト群 | `TestRBACEngine` |

---

## 5. DB モックパターン

### 5.1 app.dependency_overrides を使用したモック

```python
# tests/unit/test_api/test_users_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.core.dependencies import get_db, get_current_user
from app.models.user import User


@pytest.fixture
def mock_db_session():
    """AsyncSession の完全モック"""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.refresh = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    return session


@pytest.fixture
def override_get_db(mock_db_session):
    """get_db 依存関係のオーバーライド"""
    async def _override():
        yield mock_db_session
    return _override


@pytest.fixture
def override_get_current_user(mock_current_user):
    """get_current_user 依存関係のオーバーライド"""
    async def _override():
        return mock_current_user
    return _override


@pytest.fixture
async def async_client(override_get_db, override_get_current_user):
    """DB・認証をモック化した非同期テストクライアント"""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    # テスト後にオーバーライドをクリア
    app.dependency_overrides.clear()


class TestUsersGetList:

    @pytest.mark.asyncio
    async def test_get_users_when_authenticated_then_returns_list(
        self, async_client, mock_db_session
    ):
        # モックの戻り値設定
        mock_users = [
            MagicMock(spec=User, id=1, email="user1@example.com", username="user1"),
            MagicMock(spec=User, id=2, email="user2@example.com", username="user2"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_db_session.execute.return_value = mock_result

        response = await async_client.get("/api/v1/users")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        mock_db_session.execute.assert_called_once()
```

### 5.2 AsyncMock + MagicMock パターン詳細

```python
# モックパターン集

# パターン1: 単一オブジェクト返却
mock_db_session.scalar.return_value = mock_user_object

# パターン2: リスト返却（scalars チェーン）
mock_result = MagicMock()
mock_result.scalars.return_value.all.return_value = [user1, user2]
mock_db_session.execute.return_value = mock_result

# パターン3: None 返却（存在しないリソース）
mock_db_session.scalar.return_value = None

# パターン4: 例外発生
from sqlalchemy.exc import IntegrityError
mock_db_session.commit.side_effect = IntegrityError(
    "Duplicate entry", params=None, orig=None
)

# パターン5: 非同期コンテキストマネージャモック
mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
mock_db_session.__aexit__ = AsyncMock(return_value=None)

# パターン6: 外部 API コネクタモック
with patch("app.connectors.keycloak_connector.KeycloakConnector") as mock_kc:
    mock_kc.return_value.get_user = AsyncMock(return_value={"id": "keycloak-uuid"})
    ...
```

### 5.3 Celery タスクモック

```python
# 非同期タスクのモック
from unittest.mock import patch

@pytest.mark.asyncio
async def test_create_user_when_valid_then_sends_notification(
    self, async_client, mock_db_session
):
    with patch("app.tasks.notification.send_welcome_email.delay") as mock_task:
        response = await async_client.post("/api/v1/users", json={...})
        assert response.status_code == 201
        mock_task.assert_called_once()
```

---

## 6. カバレッジ計測コマンド

### 6.1 基本コマンド

```bash
# HTML レポート付きで全テスト実行
pytest --cov=app --cov-report=html:htmlcov --cov-report=term-missing

# カバレッジ閾値チェック付き（CI 用）
pytest --cov=app --cov-fail-under=95

# 特定モジュールのみのカバレッジ確認
pytest tests/unit/test_api/ --cov=app/api --cov-report=term-missing

# XML 形式レポート（SonarQube / CodeClimate 連携用）
pytest --cov=app --cov-report=xml:coverage.xml

# 並列実行（高速化）
pytest -n auto --cov=app --cov-report=html
```

### 6.2 カバレッジレポートの確認

```bash
# HTML レポートをブラウザで開く
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# コンソールで確認
pytest --cov=app --cov-report=term-missing 2>&1 | grep -E "TOTAL|MISS"
```

### 6.3 特定テストの実行

```bash
# マーカー別実行
pytest -m unit
pytest -m "unit and not slow"

# 特定クラスのみ実行
pytest tests/unit/test_api/test_users_api.py::TestUsersCreate -v

# キーワードフィルタ
pytest -k "test_create_user" -v

# 失敗したテストのみ再実行
pytest --lf -v

# 最初の失敗で停止
pytest -x --tb=short
```

---

## 7. 現在のカバレッジ状況

### 7.1 モジュール別カバレッジ（2026-03-25 時点）

| モジュール | Stmts | Miss | Cover |
|------------|-------|------|-------|
| `app/models/user.py` | 87 | 1 | 99% |
| `app/models/role.py` | 63 | 2 | 97% |
| `app/models/access_request.py` | 74 | 1 | 99% |
| `app/models/audit_log.py` | 52 | 2 | 96% |
| `app/api/v1/users.py` | 143 | 4 | 97% |
| `app/api/v1/auth.py` | 98 | 2 | 98% |
| `app/api/v1/roles.py` | 87 | 3 | 97% |
| `app/api/v1/access_requests.py` | 112 | 3 | 97% |
| `app/api/v1/audit_logs.py` | 76 | 4 | 95% |
| `app/core/security.py` | 45 | 0 | 100% |
| `app/core/dependencies.py` | 38 | 1 | 97% |
| `app/engine/rbac_engine.py` | 92 | 3 | 97% |
| `app/engine/policy_engine.py` | 68 | 3 | 96% |
| `app/connectors/ldap_connector.py` | 54 | 3 | 94% |
| `app/connectors/keycloak_connector.py` | 71 | 4 | 94% |
| **TOTAL** | **1,862** | **56** | **97%** |

### 7.2 テスト実行サマリー

```
==================== test session results ====================
platform linux -- Python 3.11.9, pytest-8.1.1

collected 273 items

tests/unit/test_models/     ............ [ 15%]
tests/unit/test_api/        .......................... [ 52%]
tests/unit/test_core/       ......... [ 62%]
tests/unit/test_engine/     .............. [ 77%]
tests/unit/test_connectors/ ............ [100%]

==================== 273 passed in 44.82s ====================

---------- coverage: app ----------
TOTAL    1862    56    97%
```

---

## 8. テストケース命名規則

### 8.1 命名パターン

```
test_{操作}_{条件/前提}_then_{期待結果}
```

### 8.2 命名規則例一覧

| パターン | 例 |
|----------|----|
| 正常系（作成） | `test_create_user_when_valid_data_then_returns_201` |
| 正常系（取得） | `test_get_user_when_exists_then_returns_user_data` |
| 正常系（更新） | `test_update_user_when_valid_patch_then_returns_updated` |
| 正常系（削除） | `test_delete_user_when_exists_then_returns_204` |
| 認証エラー | `test_get_users_when_unauthenticated_then_returns_401` |
| 認可エラー | `test_delete_user_when_insufficient_role_then_returns_403` |
| Not Found | `test_get_user_when_not_exists_then_returns_404` |
| バリデーション | `test_create_user_when_invalid_email_then_returns_422` |
| 重複エラー | `test_create_user_when_duplicate_email_then_returns_409` |
| RBAC 検証 | `test_access_resource_when_role_viewer_then_read_only_allowed` |
| ページネーション | `test_get_users_when_page_2_then_returns_second_page` |
| フィルタ | `test_get_users_when_filter_by_role_then_returns_filtered` |

### 8.3 禁止パターン

```python
# 悪い例（何をテストしているか不明）
def test_user():  ...
def test_api_1():  ...
def test_success():  ...

# 良い例（条件と期待結果が明確）
def test_get_user_by_id_when_valid_id_then_returns_user_details(): ...
def test_create_user_when_password_too_short_then_returns_422(): ...
def test_get_audit_logs_when_date_range_filter_then_returns_in_range(): ...
```

---

## 9. テストフィクスチャ設計

### 9.1 共通フィクスチャ一覧

```python
# tests/conftest.py （主要フィクスチャ）

@pytest.fixture(scope="session")
def sample_user_data():
    """テスト用ユーザーデータ（セッションスコープ）"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "SecurePass123!",
        "roles": ["viewer"],
    }

@pytest.fixture
def sample_role_data():
    """テスト用ロールデータ"""
    return {
        "name": "viewer",
        "description": "読み取り専用ロール",
        "permissions": ["users:read", "audit_logs:read"],
    }

@pytest.fixture
def jwt_token(mock_current_user):
    """テスト用 JWT トークン"""
    from app.core.security import create_access_token
    return create_access_token(data={"sub": mock_current_user.email})

@pytest.fixture
def auth_headers(jwt_token):
    """認証ヘッダー"""
    return {"Authorization": f"Bearer {jwt_token}"}
```

---

*最終更新: 2026-03-25 | 文書番号: TST-UNIT-001 | バージョン: 1.0.0*
