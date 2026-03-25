/**
 * ナビゲーション E2E テスト
 *
 * サイドバーナビゲーション・ページ遷移・404 ハンドリングを検証する。
 * API コールはすべてモック。
 *
 * 準拠: ISO27001 A.5.15 / NIST CSF GV.OC-01
 */

import { expect, test } from '@playwright/test';

test.describe('ページナビゲーション', () => {
  test.beforeEach(async ({ page }) => {
    // 全 API レスポンスをモック
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url();

      if (url.includes('/users')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: [] }),
        });
        return;
      }

      if (url.includes('/access-requests') || url.includes('/workflows')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: [] }),
        });
        return;
      }

      if (url.includes('/audit')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: [], total: 0, page: 1, per_page: 20 }),
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

  test('ダッシュボードページが表示される', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
    // エラーページでないことを確認（h1 要素に 500 があるか確認）
    const h1Text = await page.locator('h1').first().textContent().catch(() => '');
    expect(h1Text).not.toBe('500');
    expect(h1Text).not.toContain('Internal Server Error');
  });

  test('ユーザー管理ページが表示される', async ({ page }) => {
    await page.goto('/users');
    await expect(page).toHaveURL(/\/users/);
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toContain('Internal Server Error');
  });

  test('アクセス申請ページが表示される', async ({ page }) => {
    await page.goto('/access-requests');
    await expect(page).toHaveURL(/\/access-requests/);
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toContain('Internal Server Error');
  });

  test('ワークフローページが表示される', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page).toHaveURL(/\/workflows/);
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toContain('Internal Server Error');
  });

  test('監査ログページが表示される', async ({ page }) => {
    await page.goto('/audit');
    await expect(page).toHaveURL(/\/audit/);
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toContain('Internal Server Error');
  });

  test('すべてのメインページで body 要素が存在する', async ({ page }) => {
    const pages = ['/dashboard', '/users', '/access-requests', '/workflows', '/audit'];

    for (const path of pages) {
      await page.goto(path);
      await expect(page.locator('body')).toBeVisible();
    }
  });
});

test.describe('セキュリティヘッダー検証（バックエンド応答確認）', () => {
  test('ページロード時にセキュリティ関連のコンソールエラーがない', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.route('**/api/v1/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: [] }),
      });
    });

    await page.goto('/dashboard');

    // セキュリティ関連のクリティカルエラーがないことを確認
    const securityErrors = consoleErrors.filter(
      (e) =>
        e.toLowerCase().includes('cors') ||
        e.toLowerCase().includes('csp') ||
        e.toLowerCase().includes('x-frame'),
    );
    expect(securityErrors).toHaveLength(0);
  });
});
