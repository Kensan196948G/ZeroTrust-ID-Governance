# E2E テスト仕様（E2E Test Specification）

| 項目 | 内容 |
|------|------|
| 文書番号 | TST-E2E-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | ZeroTrust-ID-Governance 開発チーム |
| ステータス | 承認済み |

---

## 1. 概要

E2E テストは、エンドユーザーの視点からシステム全体の動作を検証します。ZeroTrust-ID-Governance では 2 種類の E2E テストを実施します。

| ツール | 対象 | 目的 |
|--------|------|------|
| **Playwright** | フロントエンド（ブラウザ操作） | UI/UX フロー・ナビゲーションの検証 |
| **Newman** | バックエンド API | API エンドポイントの実際の HTTP 動作検証 |

### 1.1 E2E テスト対象システム構成

```mermaid
graph TD
    PW[Playwright テスト] --> UI[Next.js フロントエンド]
    NW[Newman テスト] --> API[FastAPI バックエンド]
    UI --> API
    API --> DB[(PostgreSQL)]
    API --> REDIS[(Redis)]
    API --> KC[Keycloak]

    style PW fill:#1e90ff,color:#fff
    style NW fill:#ff6b35,color:#fff
    style UI fill:#61dafb,color:#333
    style API fill:#009688,color:#fff
```

---

## 2. Playwright フロントエンド E2E テスト仕様

### 2.1 対象ページ一覧

| ページ | URL | テストシナリオ数 | 優先度 |
|--------|-----|-----------------|--------|
| ログイン | `/login` | 5 | 最高 |
| ダッシュボード | `/dashboard` | 4 | 高 |
| ユーザー管理 | `/users` | 8 | 高 |
| ユーザー詳細 | `/users/:id` | 4 | 中 |
| アクセス申請 | `/access-requests` | 6 | 高 |
| アクセス申請詳細 | `/access-requests/:id` | 3 | 中 |
| 監査ログ | `/audit-logs` | 4 | 高 |
| ロール管理 | `/roles` | 4 | 中 |
| 設定 | `/settings` | 2 | 低 |

### 2.2 playwright.config.ts 設定

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["json", { outputFile: "playwright-report/results.json" }],
    ["junit", { outputFile: "playwright-report/junit.xml" }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    // セットアップ（認証状態の準備）
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    // Chrome（メインブラウザ）
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
    // Firefox
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
    // モバイル Chrome
    {
      name: "mobile-chrome",
      use: {
        ...devices["Pixel 5"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

### 2.3 認証フローテスト

```typescript
// e2e/auth/login.spec.ts
import { test, expect } from "@playwright/test";

test.describe("ログイン機能", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("有効な資格情報でログインするとダッシュボードに遷移する", async ({
    page,
  }) => {
    await page.fill('[data-testid="email-input"]', "admin@example.com");
    await page.fill('[data-testid="password-input"]', "AdminPass123!");
    await page.click('[data-testid="login-button"]');

    await expect(page).toHaveURL("/dashboard");
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
    await expect(page.locator('[data-testid="dashboard-title"]')).toContainText(
      "ダッシュボード"
    );
  });

  test("無効なパスワードでエラーメッセージが表示される", async ({ page }) => {
    await page.fill('[data-testid="email-input"]', "admin@example.com");
    await page.fill('[data-testid="password-input"]', "WrongPassword!");
    await page.click('[data-testid="login-button"]');

    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText(
      "メールアドレスまたはパスワードが正しくありません"
    );
    await expect(page).toHaveURL("/login");
  });

  test("空のフォームで送信するとバリデーションエラーが表示される", async ({
    page,
  }) => {
    await page.click('[data-testid="login-button"]');

    await expect(
      page.locator('[data-testid="email-error"]')
    ).toContainText("必須項目です");
    await expect(
      page.locator('[data-testid="password-error"]')
    ).toContainText("必須項目です");
  });

  test("ログアウト後に保護ページにアクセスするとログイン画面にリダイレクトされる", async ({
    page,
  }) => {
    // ログイン
    await page.fill('[data-testid="email-input"]', "admin@example.com");
    await page.fill('[data-testid="password-input"]', "AdminPass123!");
    await page.click('[data-testid="login-button"]');
    await expect(page).toHaveURL("/dashboard");

    // ログアウト
    await page.click('[data-testid="user-menu"]');
    await page.click('[data-testid="logout-button"]');
    await expect(page).toHaveURL("/login");

    // 保護ページに直接アクセス
    await page.goto("/dashboard");
    await expect(page).toHaveURL("/login");
  });

  test("MFA が有効なユーザーは TOTP 入力画面が表示される", async ({ page }) => {
    await page.fill('[data-testid="email-input"]', "mfa_user@example.com");
    await page.fill('[data-testid="password-input"]', "MFAPass123!");
    await page.click('[data-testid="login-button"]');

    await expect(page.locator('[data-testid="totp-input"]')).toBeVisible();
    await expect(page).toHaveURL("/login/mfa");
  });
});
```

### 2.4 認証セットアップ（グローバル認証状態）

```typescript
// e2e/auth/setup.ts
import { test as setup, expect } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, "../.auth/user.json");

setup("認証状態のセットアップ", async ({ page }) => {
  await page.goto("/login");
  await page.fill('[data-testid="email-input"]', "admin@example.com");
  await page.fill('[data-testid="password-input"]', "AdminPass123!");
  await page.click('[data-testid="login-button"]');

  await expect(page).toHaveURL("/dashboard");

  // 認証状態をファイルに保存（他テストで再利用）
  await page.context().storageState({ path: authFile });
});
```

### 2.5 ナビゲーションテスト

```typescript
// e2e/navigation/navigation.spec.ts
import { test, expect } from "@playwright/test";

test.describe("ナビゲーション", () => {
  test("サイドバーから各ページに遷移できる", async ({ page }) => {
    await page.goto("/dashboard");

    const navigationItems = [
      { testId: "nav-users", expectedUrl: "/users", title: "ユーザー管理" },
      {
        testId: "nav-access-requests",
        expectedUrl: "/access-requests",
        title: "アクセス申請",
      },
      {
        testId: "nav-audit-logs",
        expectedUrl: "/audit-logs",
        title: "監査ログ",
      },
      { testId: "nav-roles", expectedUrl: "/roles", title: "ロール管理" },
    ];

    for (const item of navigationItems) {
      await page.click(`[data-testid="${item.testId}"]`);
      await expect(page).toHaveURL(item.expectedUrl);
      await expect(
        page.locator('[data-testid="page-title"]')
      ).toContainText(item.title);
    }
  });

  test("パンくずリストが正しく表示される", async ({ page }) => {
    await page.goto("/users/1");
    const breadcrumb = page.locator('[data-testid="breadcrumb"]');
    await expect(breadcrumb).toContainText("ホーム");
    await expect(breadcrumb).toContainText("ユーザー管理");
    await expect(breadcrumb).toContainText("ユーザー詳細");
  });
});
```

### 2.6 ユーザー管理 E2E テスト

```typescript
// e2e/users/user-management.spec.ts
import { test, expect } from "@playwright/test";

test.describe("ユーザー管理", () => {
  test("ユーザー一覧が表示される", async ({ page }) => {
    await page.goto("/users");
    await expect(page.locator('[data-testid="users-table"]')).toBeVisible();
    const rows = page.locator('[data-testid="user-row"]');
    await expect(rows).not.toHaveCount(0);
  });

  test("ユーザー検索が機能する", async ({ page }) => {
    await page.goto("/users");
    await page.fill('[data-testid="search-input"]', "admin");
    await page.waitForTimeout(500); // デバウンス待機
    const rows = page.locator('[data-testid="user-row"]');
    const count = await rows.count();
    for (let i = 0; i < count; i++) {
      await expect(rows.nth(i)).toContainText("admin");
    }
  });

  test("新規ユーザー作成フォームが正常に動作する", async ({ page }) => {
    await page.goto("/users");
    await page.click('[data-testid="create-user-button"]');
    await expect(page.locator('[data-testid="user-form-modal"]')).toBeVisible();

    await page.fill('[data-testid="username-input"]', "newuser_e2e");
    await page.fill('[data-testid="email-input"]', "newuser_e2e@example.com");
    await page.fill('[data-testid="fullname-input"]', "E2E Test User");
    await page.selectOption('[data-testid="role-select"]', "viewer");
    await page.click('[data-testid="submit-button"]');

    await expect(
      page.locator('[data-testid="success-toast"]')
    ).toContainText("ユーザーを作成しました");
    await expect(
      page.locator('[data-testid="users-table"]')
    ).toContainText("newuser_e2e");
  });
});
```

### 2.7 監査ログ E2E テスト

```typescript
// e2e/audit-logs/audit-log.spec.ts
import { test, expect } from "@playwright/test";

test.describe("監査ログ", () => {
  test("監査ログ一覧が表示される", async ({ page }) => {
    await page.goto("/audit-logs");
    await expect(
      page.locator('[data-testid="audit-logs-table"]')
    ).toBeVisible();
  });

  test("日付範囲フィルターが機能する", async ({ page }) => {
    await page.goto("/audit-logs");
    await page.fill('[data-testid="date-from-input"]', "2026-03-01");
    await page.fill('[data-testid="date-to-input"]', "2026-03-25");
    await page.click('[data-testid="apply-filter-button"]');

    await expect(
      page.locator('[data-testid="filter-indicator"]')
    ).toContainText("2026-03-01 〜 2026-03-25");
  });

  test("CSV エクスポートが実行される", async ({ page }) => {
    await page.goto("/audit-logs");
    const downloadPromise = page.waitForEvent("download");
    await page.click('[data-testid="export-csv-button"]');
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/audit_log.*\.csv/);
  });
});
```

---

## 3. Newman バックエンド API E2E テスト仕様

### 3.1 Postman コレクション構成

```
zerotrust_api_e2e.postman_collection.json
├── 01_Authentication
│   ├── POST /auth/login (有効な資格情報)
│   ├── POST /auth/login (無効なパスワード → 401)
│   ├── POST /auth/refresh (リフレッシュトークン)
│   └── POST /auth/logout
├── 02_Users
│   ├── GET  /users (一覧取得)
│   ├── POST /users (ユーザー作成)
│   ├── GET  /users/:id (単件取得)
│   ├── PATCH /users/:id (更新)
│   └── DELETE /users/:id (削除)
├── 03_Roles
│   ├── GET  /roles (ロール一覧)
│   ├── POST /roles (ロール作成)
│   ├── GET  /roles/:id (ロール詳細)
│   └── DELETE /roles/:id (ロール削除)
├── 04_AccessRequests
│   ├── POST /access-requests (申請作成)
│   ├── GET  /access-requests (申請一覧)
│   ├── GET  /access-requests/:id (申請詳細)
│   ├── POST /access-requests/:id/approve (承認)
│   └── POST /access-requests/:id/reject (却下)
├── 05_AuditLogs
│   ├── GET /audit-logs (ログ一覧)
│   ├── GET /audit-logs?date_from=...&date_to=... (日付フィルター)
│   └── GET /audit-logs/export (CSV エクスポート)
└── 06_HealthCheck
    └── GET /health
```

### 3.2 Postman コレクション（重要リクエスト例）

```json
{
  "info": {
    "name": "ZeroTrust-ID-Governance API E2E",
    "_postman_id": "zerotrust-api-e2e-v1",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "01_Authentication",
      "item": [
        {
          "name": "ログイン - 有効な資格情報",
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "pm.test('Status code is 200', () => {",
                  "  pm.response.to.have.status(200);",
                  "});",
                  "pm.test('Response has access_token', () => {",
                  "  const body = pm.response.json();",
                  "  pm.expect(body).to.have.property('access_token');",
                  "  pm.expect(body).to.have.property('refresh_token');",
                  "  pm.expect(body.token_type).to.equal('bearer');",
                  "  // 後続テスト用にトークンを保存",
                  "  pm.environment.set('access_token', body.access_token);",
                  "  pm.environment.set('refresh_token', body.refresh_token);",
                  "});"
                ]
              }
            }
          ],
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/v1/auth/login",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": {
              "mode": "raw",
              "raw": "{\"email\": \"{{admin_email}}\", \"password\": \"{{admin_password}}\"}"
            }
          }
        },
        {
          "name": "ログイン - 無効なパスワード (401)",
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "pm.test('Status code is 401', () => {",
                  "  pm.response.to.have.status(401);",
                  "});",
                  "pm.test('Error message is present', () => {",
                  "  const body = pm.response.json();",
                  "  pm.expect(body).to.have.property('detail');",
                  "});"
                ]
              }
            }
          ],
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/v1/auth/login",
            "body": {
              "mode": "raw",
              "raw": "{\"email\": \"{{admin_email}}\", \"password\": \"WrongPassword!\"}"
            }
          }
        }
      ]
    }
  ]
}
```

### 3.3 環境変数設定（newman_environment.json）

```json
{
  "id": "zerotrust-e2e-environment",
  "name": "ZeroTrust E2E Environment",
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
      "value": "AdminPass123!",
      "enabled": true,
      "type": "secret"
    },
    {
      "key": "access_token",
      "value": "",
      "enabled": true,
      "description": "ログイン後に自動設定される"
    },
    {
      "key": "refresh_token",
      "value": "",
      "enabled": true,
      "description": "ログイン後に自動設定される"
    },
    {
      "key": "created_user_id",
      "value": "",
      "enabled": true,
      "description": "ユーザー作成後に自動設定される"
    },
    {
      "key": "created_role_id",
      "value": "",
      "enabled": true,
      "description": "ロール作成後に自動設定される"
    }
  ]
}
```

### 3.4 Newman 実行コマンド

```bash
# 基本実行
newman run e2e/collections/zerotrust_api_e2e.postman_collection.json \
  --environment e2e/environments/local.json \
  --reporters cli,json,junit \
  --reporter-json-export e2e/results/newman_results.json \
  --reporter-junit-export e2e/results/newman_junit.xml

# CI 環境向け実行（詳細レポート付き）
newman run e2e/collections/zerotrust_api_e2e.postman_collection.json \
  --environment e2e/environments/ci.json \
  --bail \
  --timeout-request 10000 \
  --reporters cli,json,junit,htmlextra \
  --reporter-htmlextra-export e2e/results/newman_report.html \
  --reporter-htmlextra-title "ZeroTrust API E2E Report"

# ステージング環境向け実行
newman run e2e/collections/zerotrust_api_e2e.postman_collection.json \
  --environment e2e/environments/staging.json \
  --env-var "admin_password=${STAGING_ADMIN_PASSWORD}"

# 特定フォルダのみ実行
newman run e2e/collections/zerotrust_api_e2e.postman_collection.json \
  --environment e2e/environments/local.json \
  --folder "01_Authentication" \
  --folder "02_Users"
```

### 3.5 Newman 環境別設定ファイル

```json
// e2e/environments/ci.json
{
  "id": "zerotrust-ci-environment",
  "name": "ZeroTrust CI Environment",
  "values": [
    { "key": "base_url", "value": "http://localhost:8000", "enabled": true },
    { "key": "admin_email", "value": "admin@example.com", "enabled": true },
    { "key": "admin_password", "value": "{{CI_ADMIN_PASSWORD}}", "enabled": true }
  ]
}
```

---

## 4. CI 統合（GitHub Actions）

### 4.1 GitHub Actions ワークフロー

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  pull_request:
    branches: [main, develop]
  workflow_dispatch:

jobs:
  playwright-e2e:
    name: Playwright E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: zerotrust_e2e
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4

      - name: Python セットアップ
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: バックエンド起動
        run: |
          pip install -r requirements.txt
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
        env:
          DATABASE_URL: postgresql+asyncpg://testuser:testpassword@localhost:5432/zerotrust_e2e

      - name: Node.js セットアップ
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - name: フロントエンド依存関係インストール
        run: npm ci
        working-directory: ./frontend

      - name: Playwright ブラウザインストール
        run: npx playwright install --with-deps chromium firefox

      - name: フロントエンド起動
        run: npm run start &
        working-directory: ./frontend
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000

      - name: Playwright テスト実行
        run: npx playwright test --reporter=github,html,junit
        env:
          PLAYWRIGHT_BASE_URL: http://localhost:3000
          CI: true

      - name: Playwright レポートアップロード
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 7

  newman-api-e2e:
    name: Newman API E2E Tests
    runs-on: ubuntu-latest
    needs: []  # Playwright と並行実行
    timeout-minutes: 15

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: zerotrust_api_e2e
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4

      - name: Python セットアップ・バックエンド起動
        run: |
          pip install -r requirements.txt
          python -m alembic upgrade head
          uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning &
          sleep 5
        env:
          DATABASE_URL: postgresql+asyncpg://testuser:testpassword@localhost:5432/zerotrust_api_e2e

      - name: Newman インストール
        run: npm install -g newman newman-reporter-htmlextra

      - name: API E2E テスト実行
        run: |
          newman run e2e/collections/zerotrust_api_e2e.postman_collection.json \
            --environment e2e/environments/ci.json \
            --env-var "admin_password=${{ secrets.CI_ADMIN_PASSWORD }}" \
            --bail \
            --timeout-request 10000 \
            --reporters cli,json,junit,htmlextra \
            --reporter-json-export e2e/results/newman_results.json \
            --reporter-junit-export e2e/results/newman_junit.xml \
            --reporter-htmlextra-export e2e/results/newman_report.html

      - name: Newman レポートアップロード
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: newman-report
          path: e2e/results/
          retention-days: 7

      - name: テスト結果をコメントに追加
        uses: actions/github-script@v7
        if: github.event_name == 'pull_request' && always()
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(
              fs.readFileSync('e2e/results/newman_results.json', 'utf8')
            );
            const run = results.run;
            const comment = `## Newman API E2E テスト結果
            | 項目 | 値 |
            |------|-----|
            | 総リクエスト数 | ${run.stats.requests.total} |
            | 成功 | ${run.stats.requests.total - run.stats.requests.failed} |
            | 失敗 | ${run.stats.requests.failed} |
            | 総アサーション数 | ${run.stats.assertions.total} |
            | アサーション失敗 | ${run.stats.assertions.failed} |
            `;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

### 4.2 E2E テスト実行フロー

```mermaid
sequenceDiagram
    participant PR as Pull Request
    participant CI as GitHub Actions
    participant PW as Playwright
    participant NW as Newman
    participant Art as Artifacts

    PR->>CI: PR 作成 / コミット push
    CI->>CI: バックエンド起動（FastAPI）
    CI->>CI: フロントエンド起動（Next.js）

    par Playwright と Newman を並行実行
        CI->>PW: npx playwright test
        PW->>PW: ログインテスト
        PW->>PW: ナビゲーションテスト
        PW->>PW: ユーザー管理テスト
        PW->>PW: 監査ログテスト
        PW-->>CI: HTML レポート生成
    and
        CI->>NW: newman run ...
        NW->>NW: 認証 API テスト
        NW->>NW: ユーザー API テスト
        NW->>NW: RBAC API テスト
        NW->>NW: 監査ログ API テスト
        NW-->>CI: JSON/JUnit レポート生成
    end

    CI->>Art: レポートをアーティファクトとして保存
    CI->>PR: テスト結果をコメント投稿
    alt 全テスト PASS
        CI->>PR: マージ許可
    else テスト失敗
        CI->>PR: マージブロック
    end
```

---

## 5. E2E テスト品質基準

| 指標 | 目標値 | 測定方法 |
|------|--------|----------|
| Playwright テスト全パス率 | 100% | Playwright HTML レポート |
| Newman テスト全パス率 | 100% | Newman JSON レポート |
| E2E テスト実行時間（Playwright） | < 10 分 | CI ログ |
| E2E テスト実行時間（Newman） | < 5 分 | CI ログ |
| フレーキーテスト率 | < 1% | CI 履歴分析 |

---

## 6. テストデータ管理

### 6.1 E2E テスト用シードデータ

```sql
-- e2e/seeds/01_roles.sql
INSERT INTO roles (name, description, permissions) VALUES
  ('admin', '管理者', ARRAY['users:all', 'roles:all', 'audit_logs:all']),
  ('approver', '承認者', ARRAY['users:read', 'access_requests:approve']),
  ('viewer', '閲覧者', ARRAY['users:read', 'audit_logs:read']);

-- e2e/seeds/02_users.sql
INSERT INTO users (username, email, hashed_password, is_active, is_superuser) VALUES
  ('admin', 'admin@example.com', '<hashed_AdminPass123!>', true, true),
  ('approver', 'approver@example.com', '<hashed_ApprPass123!>', true, false),
  ('viewer', 'viewer@example.com', '<hashed_ViewPass123!>', true, false);
```

### 6.2 テスト後クリーンアップ

```typescript
// e2e/global-teardown.ts
import { FullConfig } from "@playwright/test";

async function globalTeardown(config: FullConfig) {
  // E2E テストで作成したデータを削除
  const response = await fetch("http://localhost:8000/api/v1/test/cleanup", {
    method: "POST",
    headers: { "X-Test-Secret": process.env.TEST_CLEANUP_SECRET! },
  });
  console.log("E2E テストデータクリーンアップ完了");
}

export default globalTeardown;
```

---

*最終更新: 2026-03-25 | 文書番号: TST-E2E-001 | バージョン: 1.0.0*
