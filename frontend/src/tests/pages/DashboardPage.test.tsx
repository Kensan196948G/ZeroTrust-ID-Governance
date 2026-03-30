import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

/**
 * DashboardPage は Server Component (async function) で、
 * fetch() で直接 API を呼び出している。
 * テストでは fetch をモックし、子コンポーネントもモックする。
 */

// 子コンポーネントを mock
vi.mock('@/components/StatCard', () => ({
  StatCard: ({ title, value }: { title: string; value: string | number }) => (
    <div data-testid="stat-card">
      <span>{title}</span>
      <span>{value}</span>
    </div>
  ),
}));

vi.mock('@/components/SystemStatusGrid', () => ({
  SystemStatusGrid: () => <div data-testid="system-status-grid">SystemStatusGrid</div>,
}));

vi.mock('@/components/RecentAuditLogs', () => ({
  RecentAuditLogs: () => <div data-testid="recent-audit-logs">RecentAuditLogs</div>,
}));

vi.mock('@/components/PendingRequestsWidget', () => ({
  PendingRequestsWidget: () => <div data-testid="pending-requests">PendingRequestsWidget</div>,
}));

import DashboardPage from '@/app/(dashboard)/dashboard/page';

// Server Component のテスト用ヘルパー: async コンポーネントを await してレンダリング
async function renderAsync(Component: () => Promise<JSX.Element>) {
  const jsx = await Component();
  return render(jsx);
}

const mockUsersData = [
  { account_status: 'active', risk_score: 80, mfa_enabled: true },
  { account_status: 'active', risk_score: 20, mfa_enabled: true },
  { account_status: 'disabled', risk_score: 75, mfa_enabled: false },
  { account_status: 'active', risk_score: 10, mfa_enabled: true },
];

const mockPendingData = [
  { id: 'req1' },
  { id: 'req2' },
  { id: 'req3' },
];

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function setupFetchMock(usersData: unknown[] = mockUsersData, pendingData: unknown[] = mockPendingData) {
    global.fetch = vi.fn((url: string | URL | Request) => {
      const urlStr = typeof url === 'string' ? url : url.toString();
      if (urlStr.includes('/api/v1/users')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ data: usersData }),
        } as Response);
      }
      if (urlStr.includes('/api/v1/access-requests/pending')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ data: pendingData }),
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({}),
      } as Response);
    }) as typeof fetch;
  }

  it('ページタイトルが表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByText('IDガバナンス ダッシュボード')).toBeInTheDocument();
    expect(screen.getByText('ゼロトラスト アイデンティティ管理の全体状況')).toBeInTheDocument();
  });

  it('4つの StatCard が表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    const statCards = screen.getAllByTestId('stat-card');
    expect(statCards).toHaveLength(4);
  });

  it('総ユーザ数が正しく計算される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByText('総ユーザ数')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument(); // 4 users
  });

  it('高リスクユーザ数が正しく計算される（risk_score >= 70）', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByText('高リスクユーザ')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // risk_score 80 and 75
  });

  it('承認待ち申請数が正しく表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByText('承認待ち申請')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument(); // 3 pending
  });

  it('MFA 有効率が正しく計算される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByText('MFA 有効率')).toBeInTheDocument();
    // 3/4 = 75%
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('SystemStatusGrid コンポーネントが表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByTestId('system-status-grid')).toBeInTheDocument();
    expect(screen.getByText(/外部システム接続状態/)).toBeInTheDocument();
  });

  it('RecentAuditLogs コンポーネントが表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByTestId('recent-audit-logs')).toBeInTheDocument();
    expect(screen.getByText(/最近の監査ログ/)).toBeInTheDocument();
  });

  it('PendingRequestsWidget コンポーネントが表示される', async () => {
    setupFetchMock();
    await renderAsync(DashboardPage);

    expect(screen.getByTestId('pending-requests')).toBeInTheDocument();
    expect(screen.getByText(/承認待ちアクセス申請/)).toBeInTheDocument();
  });

  it('API エラー時にデフォルト値（0）が表示される', async () => {
    global.fetch = vi.fn(() =>
      Promise.reject(new Error('Network error'))
    ) as typeof fetch;

    await renderAsync(DashboardPage);

    // エラー時は全て 0
    expect(screen.getByText('総ユーザ数')).toBeInTheDocument();
    const statCards = screen.getAllByTestId('stat-card');
    expect(statCards).toHaveLength(4);
    // MFA rate = 0%
    expect(screen.getByText('0%')).toBeInTheDocument();
  });
});
