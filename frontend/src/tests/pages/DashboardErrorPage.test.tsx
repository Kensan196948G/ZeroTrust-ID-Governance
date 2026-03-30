/**
 * DashboardError コンポーネントテスト（Phase 23）
 *
 * error.tsx は Next.js App Router のエラーバウンダリ。
 * 'use client' ディレクティブを持つクライアントコンポーネント。
 * reset() コールバックと window.location.href 遷移の2つの回復手段を提供する。
 *
 * 準拠: ISO27001:2022 A.8.2 テスト制御
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DashboardError from '@/app/(dashboard)/error';

describe('DashboardError', () => {
  const mockReset = vi.fn();
  const mockError = new Error('Test error') as Error & { digest?: string };

  beforeEach(() => {
    vi.clearAllMocks();
    // console.error をモック（useEffect 内で呼ばれる）
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('エラーメッセージが表示される', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(screen.getByText('ページの読み込みに失敗しました')).toBeInTheDocument();
    expect(screen.getByText(/データの取得中にエラーが発生しました/)).toBeInTheDocument();
  });

  it('再試行ボタンが表示される', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(screen.getByRole('button', { name: '再試行' })).toBeInTheDocument();
  });

  it('ダッシュボードに戻るボタンが表示される', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(screen.getByRole('button', { name: 'ダッシュボードに戻る' })).toBeInTheDocument();
  });

  it('再試行ボタンクリックで reset が呼ばれる', async () => {
    const user = userEvent.setup();
    render(<DashboardError error={mockError} reset={mockReset} />);
    await user.click(screen.getByRole('button', { name: '再試行' }));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it('エラーが useEffect で console.error に記録される', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(console.error).toHaveBeenCalledWith('Dashboard error:', mockError);
  });

  it('digest があればエラーコードが表示される', () => {
    const errorWithDigest = Object.assign(new Error('Test'), { digest: 'abc123' });
    render(<DashboardError error={errorWithDigest} reset={mockReset} />);
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it('digest がなければエラーコード行が表示されない', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(screen.queryByText(/エラーコード:/)).not.toBeInTheDocument();
  });

  it('警告アイコンが表示される', () => {
    render(<DashboardError error={mockError} reset={mockReset} />);
    expect(screen.getByText('⚠️')).toBeInTheDocument();
  });
});
