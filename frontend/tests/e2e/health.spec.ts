/**
 * ヘルスチェック E2E テスト
 *
 * フロントエンドの基本動作（ページロード・リダイレクト）を検証する。
 * バックエンド未起動でも実行可能（API コールをモック）。
 */

import { expect, test } from '@playwright/test';

test.describe('ヘルスチェック / 基本動作', () => {
  test.beforeEach(async ({ page }) => {
    // バックエンド API 呼び出しをモック（CI 環境でバックエンドが不要）
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url();

      if (url.includes('/api/v1/health')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'ok', version: '1.0.0', env: 'test' }),
        });
        return;
      }

      // その他の API は空データで返す
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: [] }),
      });
    });
  });

  test('ルート (/) にアクセスすると /dashboard にリダイレクトされる', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('ページタイトルが正しく設定されている', async ({ page }) => {
    await page.goto('/dashboard');
    const title = await page.title();
    expect(title).toBeTruthy();
    expect(title.length).toBeGreaterThan(0);
  });

  test('ダッシュボードページが正常にロードされる', async ({ page }) => {
    await page.goto('/dashboard');
    // ページが 500 エラーでないことを確認
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
    await expect(page.locator('body')).not.toContainText('500');
  });

  test('サイドバーのナビゲーションリンクが存在する', async ({ page }) => {
    await page.goto('/dashboard');
    // サイドバーの存在を確認（ナビゲーション要素）
    const nav = page.locator('nav, aside, [role="navigation"]').first();
    await expect(nav).toBeVisible({ timeout: 5000 });
  });
});
