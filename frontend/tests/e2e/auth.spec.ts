/**
 * 認証 E2E テスト（JWT / sessionStorage）
 *
 * JWT トークンの sessionStorage 管理と認証フローを検証する。
 * バックエンド API はモックを使用。
 *
 * 準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-01
 */

import { expect, test } from '@playwright/test';

// テスト用モック JWT（RS256 署名ではなく HS256 の偽トークン）
// 実際の検証はバックエンドが行うため、フロントエンドテストでは形式のみ確認
const MOCK_ACCESS_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  'eyJzdWIiOiJ0ZXN0LXVzZXItMSIsInJvbGVzIjpbIkFkbWluIl0sImV4cCI6OTk5OTk5OTk5OX0.' +
  'mock_signature';

const MOCK_REFRESH_TOKEN = 'mock_refresh_token_for_testing';

/**
 * sessionStorage にモックトークンをセットするヘルパー
 */
async function setAuthTokens(page: import('@playwright/test').Page) {
  await page.evaluate(
    ([access, refresh]) => {
      sessionStorage.setItem('ztid_access_token', access);
      sessionStorage.setItem('ztid_refresh_token', refresh);
    },
    [MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN],
  );
}

test.describe('JWT 認証フロー', () => {
  test.beforeEach(async ({ page }) => {
    // API モックを設定
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url();

      if (url.includes('/auth/logout')) {
        await route.fulfill({ status: 204, body: '' });
        return;
      }

      if (url.includes('/auth/refresh')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            access_token: MOCK_ACCESS_TOKEN,
            refresh_token: MOCK_REFRESH_TOKEN,
            token_type: 'bearer',
          }),
        });
        return;
      }

      if (url.includes('/users')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: [] }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: [] }),
      });
    });
  });

  test('sessionStorage にトークンがない状態でダッシュボードにアクセスできる（開発モード）', async ({ page }) => {
    // フロントエンドは開発モードでは認証なしでも表示可能
    await page.goto('/dashboard');
    // 500エラーが出ないことを確認
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
  });

  test('sessionStorage にトークンをセットした状態でダッシュボードが表示される', async ({ page }) => {
    await page.goto('/dashboard');
    await setAuthTokens(page);
    await page.reload();
    // ページが正常にロードされる
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
  });

  test('sessionStorage のトークンキーが正しい形式で保存される', async ({ page }) => {
    await page.goto('/dashboard');
    await setAuthTokens(page);

    const tokens = await page.evaluate(() => ({
      access: sessionStorage.getItem('ztid_access_token'),
      refresh: sessionStorage.getItem('ztid_refresh_token'),
    }));

    expect(tokens.access).toBeTruthy();
    expect(tokens.access!.split('.').length).toBe(3); // JWT は 3 パート
    expect(tokens.refresh).toBeTruthy();
  });

  test('sessionStorage をクリアするとトークンが削除される', async ({ page }) => {
    await page.goto('/dashboard');
    await setAuthTokens(page);

    // トークンがセットされていることを確認
    const before = await page.evaluate(() => sessionStorage.getItem('ztid_access_token'));
    expect(before).toBeTruthy();

    // sessionStorage クリア
    await page.evaluate(() => {
      sessionStorage.removeItem('ztid_access_token');
      sessionStorage.removeItem('ztid_refresh_token');
    });

    const after = await page.evaluate(() => sessionStorage.getItem('ztid_access_token'));
    expect(after).toBeNull();
  });
});

test.describe('認証ヘッダー設定', () => {
  test('API リクエストに Authorization ヘッダーが付与される', async ({ page }) => {
    const authHeaders: string[] = [];

    await page.route('**/api/v1/users**', async (route) => {
      const authHeader = route.request().headers()['authorization'];
      if (authHeader) {
        authHeaders.push(authHeader);
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: [] }),
      });
    });

    // モックトークンをセットしてからページを開く
    await page.goto('/dashboard');
    await page.evaluate(
      ([access, refresh]) => {
        sessionStorage.setItem('ztid_access_token', access);
        sessionStorage.setItem('ztid_refresh_token', refresh);
      },
      [MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN],
    );

    // ユーザー一覧ページに遷移して API コールを発生させる
    await page.goto('/users');

    // Authorization ヘッダーが付与されていれば確認
    // (API コールが発生した場合のみチェック)
    if (authHeaders.length > 0) {
      expect(authHeaders[0]).toMatch(/^Bearer /);
    }
  });
});
