import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// SWR mock
vi.mock('swr', () => ({
  default: vi.fn(),
}));
import useSWR from 'swr';
const mockUseSWR = vi.mocked(useSWR);

// API mock
vi.mock('@/lib/api', () => ({
  auditApi: {
    list: vi.fn(),
    exportCsv: vi.fn().mockResolvedValue(new Blob(['csv-data'], { type: 'text/csv' })),
  },
}));

// date-fns mock
vi.mock('date-fns', () => ({
  format: vi.fn((_date: Date, fmt: string) => '2025/01/01 12:00:00'),
}));
vi.mock('date-fns/locale', () => ({
  ja: {},
}));

import AuditPage from '@/app/(dashboard)/audit/page';

const mockLogs = [
  {
    id: 1,
    event_id: 'evt-001',
    event_time: '2025-01-01T12:00:00Z',
    event_type: 'USER_MANAGEMENT',
    source_system: 'EntraID',
    actor_user_id: 'user-001',
    action: 'CREATE_USER',
    result: 'success',
    risk_score: 10,
  },
  {
    id: 2,
    event_id: 'evt-002',
    event_time: '2025-01-01T13:00:00Z',
    event_type: 'ACCESS_CONTROL',
    source_system: 'ActiveDirectory',
    actor_user_id: 'user-002',
    action: 'DELETE_ROLE',
    result: 'failure',
    risk_score: 85,
  },
  {
    id: 3,
    event_id: 'evt-003',
    event_time: '2025-01-01T14:00:00Z',
    event_type: 'APPROVAL',
    source_system: 'HENGEONE',
    actor_user_id: null,
    action: 'APPROVE_REQUEST',
    result: 'success',
    risk_score: null,
  },
];

describe('AuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function setupSWR(data: typeof mockLogs | undefined, isLoading: boolean) {
    mockUseSWR.mockReturnValue({
      data,
      isLoading,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);
  }

  it('ローディング中にスケルトンが表示される', () => {
    setupSWR(undefined, true);
    const { container } = render(<AuditPage />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('監査ログが正しく表示される', () => {
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    expect(screen.getByText('CREATE_USER')).toBeInTheDocument();
    expect(screen.getByText('DELETE_ROLE')).toBeInTheDocument();
    expect(screen.getByText('APPROVE_REQUEST')).toBeInTheDocument();
    expect(screen.getByText('EntraID')).toBeInTheDocument();
    expect(screen.getByText('ActiveDirectory')).toBeInTheDocument();
    expect(screen.getByText('HENGEONE')).toBeInTheDocument();
  });

  it('検索でフィルタリングされる', async () => {
    const user = userEvent.setup();
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const searchInput = screen.getByPlaceholderText('アクション・イベント種別・ソースシステムで検索...');
    await user.type(searchInput, 'CREATE');

    expect(screen.getByText('CREATE_USER')).toBeInTheDocument();
    expect(screen.queryByText('DELETE_ROLE')).not.toBeInTheDocument();
    expect(screen.queryByText('APPROVE_REQUEST')).not.toBeInTheDocument();
  });

  it('「次へ」「前へ」ボタンでページ遷移する', async () => {
    const user = userEvent.setup();
    // 20件返すことで「次へ」ボタンが有効になる
    const fullPage = Array.from({ length: 20 }, (_, i) => ({
      ...mockLogs[0],
      id: i + 1,
      event_id: `evt-${i}`,
    }));
    setupSWR(fullPage, false);
    render(<AuditPage />);

    // 初期状態: ページ 1
    expect(screen.getByText(/ページ 1/)).toBeInTheDocument();

    // 「次へ」をクリック
    const nextButton = screen.getByText('次へ →');
    await user.click(nextButton);

    // ページが 2 になる
    expect(screen.getByText(/ページ 2/)).toBeInTheDocument();

    // 「前へ」をクリック
    const prevButton = screen.getByText('← 前へ');
    await user.click(prevButton);

    expect(screen.getByText(/ページ 1/)).toBeInTheDocument();
  });

  it('1ページ目で「前へ」が disabled', () => {
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const prevButton = screen.getByText('← 前へ');
    expect(prevButton).toBeDisabled();
  });

  it('CSV エクスポートボタンが表示される', () => {
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    expect(screen.getByText('CSV エクスポート')).toBeInTheDocument();
  });

  it('結果がsuccessの時に「成功」バッジ表示', () => {
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const successBadges = screen.getAllByText('成功');
    expect(successBadges.length).toBe(2); // CREATE_USER と APPROVE_REQUEST
  });

  it('結果がfailureの時に「失敗」バッジ表示', () => {
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    expect(screen.getByText('失敗')).toBeInTheDocument();
  });
});
