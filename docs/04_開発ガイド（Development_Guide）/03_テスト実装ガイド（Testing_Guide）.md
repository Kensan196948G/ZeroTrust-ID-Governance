# テスト実装ガイド（Testing Guide）

| 項目 | 内容 |
|------|------|
| 文書番号 | DEV-TST-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新 | 2026-03-24 |
| 対象プロジェクト | ZeroTrust-ID-Governance |
| 担当 | 開発チーム |
| ステータス | 有効 |

---

## 目次

1. [テスト方針とテストピラミッド](#1-テスト方針とテストピラミッド)
2. [pytest 設定と実行コマンド](#2-pytest-設定と実行コマンド)
3. [非同期テスト（pytest-asyncio）](#3-非同期テストpytest-asyncio)
4. [DB モックパターン](#4-db-モックパターン)
5. [カバレッジ計測](#5-カバレッジ計測)
6. [Playwright E2E テスト](#6-playwright-e2e-テスト)
7. [Newman API テスト](#7-newman-api-テスト)
8. [テストファイル命名規則](#8-テストファイル命名規則)

---

## 1. テスト方針とテストピラミッド

### 1.1 テストピラミッド

```
        /\
       /  \
      / E2E \          ← 少数・重要フロー中心
     /--------\
    / Integration\     ← API 統合テスト・DB 結合テスト
   /--------------\
  /   Unit Tests   \   ← 多数・ビジネスロジック中心
 /------------------\
```

| レイヤー | 対象 | 割合目安 | ツール |
|---------|------|---------|--------|
| **Unit** | サービス層・ユーティリティ・スキーマ | 70% | pytest, unittest.mock |
| **Integration** | API エンドポイント・DB 操作 | 25% | pytest + httpx + TestClient |
| **E2E** | 主要ユーザーフロー（認証・認可等） | 5% | Playwright / Newman |

### 1.2 テスト品質基準

| 指標 | 目標値 | 説明 |
|------|--------|------|
| ラインカバレッジ | 80% 以上 | バックエンド全体 |
| ブランチカバレッジ | 70% 以上 | 条件分岐の網羅率 |
| E2E 主要フロー | 100% | 認証・ユーザー管理・RBAC |
| CI テスト実行時間 | 5分以内 | ユニット + 統合テスト |

### 1.3 テスト原則

- **AAA パターン**（Arrange / Act / Assert）に従ってテストを記述する
- **1テスト1アサーション**を原則とする（複数の場合は明確に分ける）
- テストは**独立して実行可能**であること（順序依存を禁止）
- **テストデータはフィクスチャで管理**し、ハードコーディングを避ける
- **本番コードと同じコーディング規約**を適用する

---

## 2. pytest 設定と実行コマンド

### 2.1 pytest 設定（`pyproject.toml`）

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-v",
    "--tb=short",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",
]
markers = [
    "unit: ユニットテスト",
    "integration: 統合テスト",
    "e2e: E2E テスト",
    "slow: 実行時間が長いテスト",
    "security: セキュリティ関連テスト",
]
```

### 2.2 テスト実行コマンド

```bash
# 全テスト実行
pytest

# 特定のテストファイルを実行
pytest tests/unit/test_user_service.py

# 特定のテスト関数を実行
pytest tests/unit/test_user_service.py::TestUserService::test_create_user_success

# マーカーでフィルタリング
pytest -m unit           # ユニットテストのみ
pytest -m integration    # 統合テストのみ
pytest -m "not e2e"      # E2E 以外

# 失敗時に詳細表示
pytest -v --tb=long

# 最初の失敗で停止
pytest -x

# 失敗したテストのみ再実行
pytest --lf

# 並列実行（pytest-xdist）
pytest -n auto           # CPU コア数で自動設定
pytest -n 4              # 4並列

# Docker 環境で実行
docker compose exec backend pytest
docker compose exec backend pytest -m unit --no-cov
```

### 2.3 conftest.py の基本構成

```python
# tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# テスト用データベース URL
TEST_DATABASE_URL = settings.DATABASE_TEST_URL

# テスト用エンジン
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestAsyncSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
async def setup_database() -> AsyncGenerator[None, None]:
    """テスト用 DB のセットアップ・クリーンアップ。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_database: None) -> AsyncGenerator[AsyncSession, None]:
    """トランザクションをロールバックするテスト用 DB セッション。"""
    async with test_engine.begin() as conn:
        async with TestAsyncSessionLocal(bind=conn) as session:
            yield session
            await conn.rollback()  # テスト後にロールバック


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """テスト用 HTTP クライアント（依存性注入をオーバーライド済み）。"""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
```

---

## 3. 非同期テスト（pytest-asyncio）

### 3.1 基本的な非同期テストの書き方

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.user import UserService
from app.schemas.user import UserCreate
from app.core.exceptions import UserAlreadyExistsError


class TestUserService:
    """UserService のユニットテスト。"""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """モックリポジトリ。"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repository: AsyncMock) -> UserService:
        """テスト対象のサービスインスタンス。"""
        return UserService(repository=mock_repository)

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, service: UserService, mock_repository: AsyncMock
    ) -> None:
        """正常なユーザー作成のテスト。"""
        # Arrange
        user_data = UserCreate(
            email="test@example.com",
            password="SecurePass@123",
            display_name="Test User",
        )
        expected_user = MagicMock(id=uuid4(), email=user_data.email)
        mock_repository.get_by_email.return_value = None  # 既存ユーザーなし
        mock_repository.create.return_value = expected_user

        # Act
        result = await service.create(user_data)

        # Assert
        assert result.email == user_data.email
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises_error(
        self, service: UserService, mock_repository: AsyncMock
    ) -> None:
        """重複メールアドレスで UserAlreadyExistsError が発生することをテスト。"""
        # Arrange
        user_data = UserCreate(
            email="existing@example.com",
            password="SecurePass@123",
            display_name="Duplicate User",
        )
        existing_user = MagicMock(email=user_data.email)
        mock_repository.get_by_email.return_value = existing_user  # 既存ユーザーあり

        # Act & Assert
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await service.create(user_data)

        assert "existing@example.com" in str(exc_info.value)
        mock_repository.create.assert_not_called()
```

### 3.2 asyncio_mode = "auto" の活用

`pyproject.toml` で `asyncio_mode = "auto"` を設定すると、`@pytest.mark.asyncio` デコレータを省略できます。

```python
# asyncio_mode = "auto" 設定時は @pytest.mark.asyncio 不要
class TestAuthService:
    async def test_login_success(self, service: AuthService) -> None:
        """ログイン成功テスト（asyncio_mode=auto により自動検出）。"""
        # Arrange
        credentials = LoginRequest(email="user@example.com", password="Pass@123")

        # Act
        tokens = await service.login(credentials)

        # Assert
        assert tokens.access_token is not None
        assert tokens.token_type == "bearer"
```

### 3.3 フィクスチャのスコープ

```python
import pytest_asyncio

# function スコープ（デフォルト）: 各テスト関数ごとに実行
@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    user = await create_test_user(db_session)
    return user

# module スコープ: テストモジュール全体で1回
@pytest_asyncio.fixture(scope="module")
async def shared_resource() -> AsyncGenerator[Resource, None]:
    resource = await Resource.create()
    yield resource
    await resource.cleanup()

# session スコープ: テストセッション全体で1回
@pytest_asyncio.fixture(scope="session")
async def database_setup() -> AsyncGenerator[None, None]:
    await setup_test_database()
    yield
    await teardown_test_database()
```

---

## 4. DB モックパターン

### 4.1 `dependency_overrides` を使った DB モック

FastAPI の `dependency_overrides` を使って、テスト時に DB セッションを差し替えます。

```python
# tests/integration/test_user_api.py
import pytest
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_db


@pytest.fixture
async def async_client_with_db(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """DB セッションをオーバーライドした HTTP クライアント。"""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # 依存性注入をオーバーライド
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    # テスト終了後にオーバーライドをクリア
    app.dependency_overrides.clear()


class TestUserAPI:
    async def test_get_user_returns_200(
        self, async_client_with_db: AsyncClient, test_user: User
    ) -> None:
        """ユーザー取得 API が 200 を返すことをテスト。"""
        # Arrange
        headers = {"Authorization": f"Bearer {test_user.access_token}"}

        # Act
        response = await async_client_with_db.get(
            f"/api/v1/users/{test_user.id}",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
```

### 4.2 認証依存性のモック

```python
from app.core.deps import get_current_user
from app.models.user import User


@pytest.fixture
def mock_current_user() -> User:
    """認証済みユーザーのモック。"""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "testuser@example.com"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def authenticated_client(
    async_client: AsyncClient,
    mock_current_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """認証済みクライアント（JWT 検証をバイパス）。"""
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    yield async_client
    app.dependency_overrides.pop(get_current_user, None)
```

### 4.3 Redis モックパターン

```python
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Redis クライアントのモック。"""
    with patch("app.core.cache.redis_client") as mock:
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=0)
        yield mock


class TestTokenBlacklist:
    async def test_revoke_token(
        self, service: TokenService, mock_redis: AsyncMock
    ) -> None:
        """トークン失効化のテスト。"""
        # Arrange
        token = "test.jwt.token"

        # Act
        await service.revoke_token(token)

        # Assert
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "blacklist" in call_args[0][0]
```

### 4.4 外部サービスモックパターン

```python
from unittest.mock import patch, AsyncMock
import pytest


class TestEmailService:
    @patch("app.services.email.smtp_client.send", new_callable=AsyncMock)
    async def test_send_verification_email(self, mock_send: AsyncMock) -> None:
        """メール送信サービスのモックテスト。"""
        # Arrange
        mock_send.return_value = {"message_id": "test-id-123"}
        email_service = EmailService()

        # Act
        result = await email_service.send_verification_email(
            to="user@example.com",
            verification_token="abc123"
        )

        # Assert
        assert result is True
        mock_send.assert_called_once_with(
            to="user@example.com",
            subject="メールアドレスの確認",
        )
```

---

## 5. カバレッジ計測

### 5.1 カバレッジレポートの生成

```bash
# テスト実行 + カバレッジ計測
pytest --cov=app --cov-report=term-missing

# HTML レポート生成
pytest --cov=app --cov-report=html:htmlcov

# XML レポート（CI 連携用）
pytest --cov=app --cov-report=xml:coverage.xml

# 複数形式で同時出力
pytest \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=html:htmlcov \
  --cov-report=xml:coverage.xml

# カバレッジが基準値を下回った場合にテスト失敗にする
pytest --cov=app --cov-fail-under=80
```

### 5.2 カバレッジ設定（`.coveragerc`）

```ini
[run]
source = app
omit =
    app/main.py          # アプリエントリポイント
    app/core/config.py   # 設定クラス
    alembic/*            # マイグレーション
    tests/*              # テスト自体は除外

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
    @overload
```

### 5.3 カバレッジ除外の使い方

```python
def deprecated_method(self) -> None:  # pragma: no cover
    """廃止予定のメソッド。テスト対象外。"""
    raise DeprecationWarning("このメソッドは廃止されました")
```

### 5.4 カバレッジレポートの確認

```bash
# HTML レポートをブラウザで開く
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux

# カバレッジ率のみ確認
coverage report --include="app/**"

# 未カバー行の確認
coverage report -m --include="app/services/**"
```

---

## 6. Playwright E2E テスト

### 6.1 Playwright のセットアップ

```bash
cd frontend

# Playwright のインストール
npm install -D @playwright/test

# ブラウザのインストール
npx playwright install chromium firefox webkit

# または最小限（CI 用）
npx playwright install --with-deps chromium
```

### 6.2 Playwright 設定（`playwright.config.ts`）

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
```

### 6.3 E2E テストの書き方

```typescript
// tests/e2e/auth.spec.ts
import { test, expect } from "@playwright/test";

test.describe("認証フロー", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("正常ログインでダッシュボードに遷移する", async ({ page }) => {
    // Arrange: ログインページが表示されている
    await expect(page.getByRole("heading", { name: "ログイン" })).toBeVisible();

    // Act: 認証情報を入力してログイン
    await page.getByLabel("メールアドレス").fill("admin@example.com");
    await page.getByLabel("パスワード").fill("Admin@12345!");
    await page.getByRole("button", { name: "ログイン" }).click();

    // Assert: ダッシュボードに遷移
    await expect(page).toHaveURL("/dashboard");
    await expect(page.getByRole("heading", { name: "ダッシュボード" })).toBeVisible();
  });

  test("誤ったパスワードでエラーメッセージが表示される", async ({ page }) => {
    // Act
    await page.getByLabel("メールアドレス").fill("admin@example.com");
    await page.getByLabel("パスワード").fill("WrongPassword!");
    await page.getByRole("button", { name: "ログイン" }).click();

    // Assert
    await expect(page.getByRole("alert")).toContainText("メールアドレスまたはパスワードが正しくありません");
    await expect(page).toHaveURL("/login");
  });
});

test.describe("権限制御（RBAC）", () => {
  test("viewer ロールはユーザー管理ページにアクセスできない", async ({ page }) => {
    // Arrange: viewer としてログイン
    await page.goto("/login");
    await page.getByLabel("メールアドレス").fill("viewer@example.com");
    await page.getByLabel("パスワード").fill("Viewer@12345!");
    await page.getByRole("button", { name: "ログイン" }).click();

    // Act: 管理者専用ページにアクセス
    await page.goto("/admin/users");

    // Assert: アクセス拒否ページが表示される
    await expect(page.getByRole("heading", { name: "アクセス権限がありません" })).toBeVisible();
  });
});
```

### 6.4 E2E テストの実行コマンド

```bash
# 全 E2E テスト実行
npx playwright test

# 特定のファイルを実行
npx playwright test tests/e2e/auth.spec.ts

# UI モードで実行（デバッグに便利）
npx playwright test --ui

# ヘッドフルモードで実行（ブラウザを表示）
npx playwright test --headed

# デバッグモードで実行
npx playwright test --debug

# 特定のブラウザで実行
npx playwright test --project=chromium

# レポートを表示
npx playwright show-report

# CI 環境での実行
CI=true npx playwright test
```

### 6.5 Page Object Model（POM）パターン

```typescript
// tests/e2e/pages/LoginPage.ts
import type { Page, Locator } from "@playwright/test";

export class LoginPage {
  private readonly page: Page;
  private readonly emailInput: Locator;
  private readonly passwordInput: Locator;
  private readonly submitButton: Locator;
  private readonly errorAlert: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByLabel("メールアドレス");
    this.passwordInput = page.getByLabel("パスワード");
    this.submitButton = page.getByRole("button", { name: "ログイン" });
    this.errorAlert = page.getByRole("alert");
  }

  async goto(): Promise<void> {
    await this.page.goto("/login");
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async getErrorMessage(): Promise<string> {
    return this.errorAlert.textContent() ?? "";
  }
}
```

---

## 7. Newman API テスト

### 7.1 Newman のセットアップ

```bash
# Newman のインストール
npm install -g newman newman-reporter-htmlextra

# または プロジェクトローカルにインストール
npm install -D newman newman-reporter-htmlextra
```

### 7.2 Postman コレクションの管理

```
tests/
└── api/
    ├── ZeroTrust-ID-Governance.postman_collection.json  # メインコレクション
    ├── environments/
    │   ├── local.postman_environment.json               # ローカル環境変数
    │   ├── staging.postman_environment.json             # ステージング環境変数
    │   └── production.postman_environment.json          # 本番環境変数
    └── newman-report/                                   # レポート出力先
```

### 7.3 Newman 実行コマンド

```bash
# ローカル環境でコレクションを実行
newman run tests/api/ZeroTrust-ID-Governance.postman_collection.json \
  --environment tests/api/environments/local.postman_environment.json

# HTML レポートを生成
newman run tests/api/ZeroTrust-ID-Governance.postman_collection.json \
  --environment tests/api/environments/local.postman_environment.json \
  --reporters cli,htmlextra \
  --reporter-htmlextra-export tests/api/newman-report/index.html

# 特定フォルダのみ実行
newman run tests/api/ZeroTrust-ID-Governance.postman_collection.json \
  --environment tests/api/environments/local.postman_environment.json \
  --folder "Authentication"

# タイムアウト設定・リトライあり
newman run tests/api/ZeroTrust-ID-Governance.postman_collection.json \
  --environment tests/api/environments/local.postman_environment.json \
  --timeout-request 10000 \
  --iteration-count 1

# CI 環境での実行（exit code を適切に返す）
newman run tests/api/ZeroTrust-ID-Governance.postman_collection.json \
  --environment tests/api/environments/staging.postman_environment.json \
  --suppress-exit-code 0
```

### 7.4 環境変数ファイルの例

```json
{
  "name": "local",
  "values": [
    {
      "key": "base_url",
      "value": "http://localhost:8000",
      "enabled": true
    },
    {
      "key": "admin_email",
      "value": "admin@example.com",
      "enabled": true
    },
    {
      "key": "admin_password",
      "value": "Admin@12345!",
      "enabled": true
    },
    {
      "key": "access_token",
      "value": "",
      "enabled": true
    }
  ]
}
```

### 7.5 Postman テストスクリプト例

```javascript
// Postman Collection のテストスクリプト（Pre-request / Tests タブ）

// ログイン後のトークン保存（Pre-request Script）
pm.test("Status code is 200", () => {
    pm.response.to.have.status(200);
});

pm.test("Response has access_token", () => {
    const json = pm.response.json();
    pm.expect(json).to.have.property("access_token");
    pm.environment.set("access_token", json.access_token);
});

pm.test("Token type is bearer", () => {
    const json = pm.response.json();
    pm.expect(json.token_type).to.equal("bearer");
});
```

---

## 8. テストファイル命名規則

### 8.1 バックエンド（Python）

| 規則 | 説明 | 例 |
|------|------|-----|
| プレフィックス `test_` | すべてのテストファイルは `test_` で開始 | `test_user_service.py` |
| 対象モジュール名を含める | テスト対象のファイル名を反映 | `test_auth_router.py` (← `auth_router.py`) |
| テストクラスは `Test` で開始 | `class TestUserService:` | |
| テスト関数は `test_` で開始 | `def test_create_user_success():` | |
| テスト内容を具体的に記述 | `test_login_with_invalid_password_returns_401` | |

```
tests/
├── conftest.py                         # 共有フィクスチャ
├── unit/
│   ├── conftest.py
│   ├── test_user_service.py
│   ├── test_auth_service.py
│   ├── test_rbac_service.py
│   └── test_token_validator.py
├── integration/
│   ├── conftest.py
│   ├── test_user_api.py               # /api/v1/users/** のテスト
│   ├── test_auth_api.py               # /api/v1/auth/** のテスト
│   └── test_role_api.py               # /api/v1/roles/** のテスト
└── e2e/
    └── test_auth_flow.py              # 認証フロー E2E テスト
```

### 8.2 フロントエンド（TypeScript）

| 規則 | 説明 | 例 |
|------|------|-----|
| `*.test.ts` / `*.test.tsx` | ユニットテスト・コンポーネントテスト | `UserCard.test.tsx` |
| `*.spec.ts` | Playwright E2E テスト | `auth.spec.ts` |
| テストファイルはテスト対象と同一ディレクトリに配置 | コロケーション原則 | `components/UserCard/UserCard.test.tsx` |

```
frontend/
├── src/
│   └── components/
│       └── UserCard/
│           ├── UserCard.tsx
│           ├── UserCard.test.tsx       # コンポーネントのユニットテスト
│           └── index.ts
└── tests/
    └── e2e/
        ├── auth.spec.ts               # 認証フロー E2E
        ├── user-management.spec.ts    # ユーザー管理 E2E
        └── rbac.spec.ts              # 権限制御 E2E
```

### 8.3 テスト関数命名パターン

```python
# Python テスト関数命名パターン
# test_<対象>_<条件>_<期待する結果>

def test_create_user_with_valid_data_returns_user() -> None: ...
def test_create_user_with_duplicate_email_raises_error() -> None: ...
def test_login_with_invalid_password_returns_401() -> None: ...
def test_get_user_without_auth_returns_403() -> None: ...
def test_revoke_token_adds_to_blacklist() -> None: ...
```

```typescript
// TypeScript テスト関数命名パターン
test("正常なデータでユーザーを作成できる", async () => { ... });
test("重複メールアドレスでエラーが発生する", async () => { ... });
test("認証なしでアクセスすると 401 が返る", async () => { ... });
```

---

*文書番号: DEV-TST-001 | バージョン: 1.0.0 | 最終更新: 2026-03-24*
