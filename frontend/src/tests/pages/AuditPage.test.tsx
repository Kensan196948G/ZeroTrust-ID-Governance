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

  it('CSV エクスポートボタンクリックでダウンロードが実行される（lines 48-55）', async () => {
    const user = userEvent.setup();
    const { auditApi } = await import('@/lib/api');

    // jsdom には URL.createObjectURL が存在しないため グローバルに定義してから spy
    const mockObjectUrl = 'blob:http://localhost/mock-url';
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn();
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue(mockObjectUrl);
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    // <a>.click() をキャプチャするため createElement をモック
    const mockClick = vi.fn();
    const mockAnchor = { href: '', download: '', click: mockClick } as unknown as HTMLAnchorElement;
    const origCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') return mockAnchor;
      return origCreateElement(tag);
    });

    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const exportButton = screen.getByText('CSV エクスポート');
    await user.click(exportButton);

    await waitFor(() => {
      expect(auditApi.exportCsv).toHaveBeenCalled();
      expect(createObjectURLSpy).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
      expect(revokeObjectURLSpy).toHaveBeenCalledWith(mockObjectUrl);
    });

    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();
    vi.spyOn(document, 'createElement').mockRestore();
  });

  it('CSV エクスポート失敗時に alert が表示される（lines 56-59）', async () => {
    const user = userEvent.setup();
    const { auditApi } = await import('@/lib/api');
    vi.mocked(auditApi.exportCsv).mockRejectedValueOnce(new Error('Forbidden'));

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const exportButton = screen.getByText('CSV エクスポート');
    await user.click(exportButton);

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith(
        expect.stringContaining('CSV エクスポートに失敗しました')
      );
      expect(consoleErrorSpy).toHaveBeenCalled();
    });

    alertSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

  it('未分類アクション（line 19：gray fallback）が正しく表示される', () => {
    const logsWithUnknownAction = [
      { ...mockLogs[0], id: 99, action: 'EXPORT_AUDIT_LOG' },
    ];
    setupSWR(logsWithUnknownAction, false);
    render(<AuditPage />);
    expect(screen.getByText('EXPORT_AUDIT_LOG')).toBeInTheDocument();
  });

  it('未知の result 値（line 25：gray fallback）が正しく表示される', () => {
    const logsWithUnknownResult = [
      { ...mockLogs[0], id: 100, result: 'partial' },
    ];
    setupSWR(logsWithUnknownResult, false);
    render(<AuditPage />);
    expect(screen.getByText('partial')).toBeInTheDocument();
  });

  it('検索結果が0件のとき「ログがありません」が表示される（lines 134-138）', async () => {
    const user = userEvent.setup();
    setupSWR(mockLogs, false);
    render(<AuditPage />);

    const searchInput = screen.getByPlaceholderText('アクション・イベント種別・ソースシステムで検索...');
    await user.type(searchInput, 'NONEXISTENT_ACTION_XYZ');

    expect(screen.getByText('ログがありません')).toBeInTheDocument();
  });
});
