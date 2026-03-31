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
  accessApi: {
    list: vi.fn(),
    approve: vi.fn().mockResolvedValue({}),
    reject: vi.fn().mockResolvedValue({}),
  },
}));
import { accessApi } from '@/lib/api';

// date-fns mock to avoid locale issues in test
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn(() => '1時間前'),
}));
vi.mock('date-fns/locale', () => ({
  ja: {},
}));

import AccessRequestsPage from '@/app/(dashboard)/access-requests/page';

const mockRequests = [
  {
    id: 'req1',
    request_type: 'grant',
    justification: 'プロジェクトAへのアクセスが必要',
    status: 'pending' as const,
    created_at: '2025-01-01T00:00:00Z',
    expires_at: '2025-06-01T00:00:00Z',
  },
  {
    id: 'req2',
    request_type: 'revoke',
    justification: '退職に伴うアクセス剥奪',
    status: 'approved' as const,
    created_at: '2025-01-02T00:00:00Z',
    expires_at: null,
  },
  {
    id: 'req3',
    request_type: 'transfer',
    justification: '部署異動に伴う権限移譲',
    status: 'rejected' as const,
    created_at: '2025-01-03T00:00:00Z',
    expires_at: null,
  },
  {
    id: 'req4',
    request_type: 'review',
    justification: '四半期棚卸',
    status: 'pending' as const,
    created_at: '2025-01-04T00:00:00Z',
    expires_at: '2025-07-01T00:00:00Z',
  },
];

const mockMutate = vi.fn();

describe('AccessRequestsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function setupSWR(data: typeof mockRequests | undefined, isLoading: boolean) {
    mockUseSWR.mockReturnValue({
      data,
      isLoading,
      error: undefined,
      mutate: mockMutate,
      isValidating: false,
    } as ReturnType<typeof useSWR>);
  }

  it('ローディング中にスケルトンが表示される', () => {
    setupSWR(undefined, true);
    const { container } = render(<AccessRequestsPage />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('申請一覧が正しく表示される', () => {
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    expect(screen.getByText('アクセス付与')).toBeInTheDocument();
    expect(screen.getByText('プロジェクトAへのアクセスが必要')).toBeInTheDocument();
    expect(screen.getByText('アクセス剥奪')).toBeInTheDocument();
    expect(screen.getByText('権限移譲')).toBeInTheDocument();
    expect(screen.getByText('棚卸')).toBeInTheDocument();
  });

  it('フィルタータブで「すべて」「承認待ち」「承認済み」「却下」を切替できる', () => {
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // フィルタータブ内のボタンを確認（rounded-full クラスを持つボタン群）
    const filterButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-full')
    );
    expect(filterButtons).toHaveLength(4);
    expect(filterButtons[0].textContent).toContain('すべて');
    expect(filterButtons[1].textContent).toContain('承認待ち');
    expect(filterButtons[2].textContent).toContain('承認済み');
    expect(filterButtons[3].textContent).toContain('却下');
  });

  it('フィルター切替で表示が絞り込まれる', async () => {
    const user = userEvent.setup();
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // 「承認待ち」タブをクリック
    const filterButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-full')
    );
    await user.click(filterButtons[1]); // 承認待ち

    // pending のみ表示される
    expect(screen.getByText('プロジェクトAへのアクセスが必要')).toBeInTheDocument();
    expect(screen.getByText('四半期棚卸')).toBeInTheDocument();
    // approved/rejected は非表示
    expect(screen.queryByText('退職に伴うアクセス剥奪')).not.toBeInTheDocument();
    expect(screen.queryByText('部署異動に伴う権限移譲')).not.toBeInTheDocument();
  });

  it('pending の申請に承認/却下ボタンが表示される', () => {
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // テーブル内のアクションボタン（rounded-lg クラスを持つ）
    const actionButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg')
    );
    // pending が2件 x (承認 + 却下) = 4ボタン
    expect(actionButtons).toHaveLength(4);
    const approveButtons = actionButtons.filter((btn) => btn.textContent?.includes('承認'));
    const rejectButtons = actionButtons.filter((btn) => btn.textContent?.includes('却下'));
    expect(approveButtons).toHaveLength(2);
    expect(rejectButtons).toHaveLength(2);
  });

  it('approved の申請にはアクションボタンが表示されない', async () => {
    const user = userEvent.setup();
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // 「承認済み」タブをクリック
    const filterButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-full')
    );
    await user.click(filterButtons[2]); // 承認済み

    // approved の申請が表示される
    expect(screen.getByText('退職に伴うアクセス剥奪')).toBeInTheDocument();
    // テーブル内のアクションボタン（rounded-lg）がないことを確認
    const actionButtons = screen.queryAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg')
    );
    expect(actionButtons).toHaveLength(0);
  });

  it('承認ボタンクリックで accessApi.approve が呼ばれる', async () => {
    const user = userEvent.setup();
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // テーブル内の承認ボタン（rounded-lg + 承認テキスト）
    const actionButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg') && btn.textContent?.includes('承認')
    );
    await user.click(actionButtons[0]);

    await waitFor(() => {
      expect(accessApi.approve).toHaveBeenCalledWith('req1');
    });
    expect(mockMutate).toHaveBeenCalled();
  });

  it('各ステータスのカウントが正しい', () => {
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    // すべて(4), 承認待ち(2), 承認済み(1), 却下(1)
    expect(screen.getByText('(4)')).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
    expect(screen.getAllByText('(1)')).toHaveLength(2);
  });

  it('却下ボタンクリックで accessApi.reject が呼ばれる（line 39）', async () => {
    const user = userEvent.setup();
    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    const rejectButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg') && btn.textContent?.includes('却下')
    );
    await user.click(rejectButtons[0]);

    await waitFor(() => {
      expect(accessApi.reject).toHaveBeenCalledWith('req1');
    });
    expect(mockMutate).toHaveBeenCalled();
  });

  it('accessApi.approve が失敗してもクラッシュしない（line 42-43 catch）', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(accessApi.approve).mockRejectedValueOnce(new Error('Network error'));

    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    const approveButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg') && btn.textContent?.includes('承認')
    );
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('承認に失敗しました'),
        expect.any(Error)
      );
    });
    consoleErrorSpy.mockRestore();
  });

  it('accessApi.reject が失敗してもクラッシュしない（line 42-43 catch）', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(accessApi.reject).mockRejectedValueOnce(new Error('Auth error'));

    setupSWR(mockRequests, false);
    render(<AccessRequestsPage />);

    const rejectButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-lg') && btn.textContent?.includes('却下')
    );
    await user.click(rejectButtons[0]);

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('却下に失敗しました'),
        expect.any(Error)
      );
    });
    consoleErrorSpy.mockRestore();
  });

  it('フィルター絞り込みで結果0件のとき「申請がありません」が表示される（lines 123-128）', async () => {
    const user = userEvent.setup();
    // approved のみのデータで「承認待ち」タブをクリックすると0件になる
    const approvedOnly = [mockRequests[1]]; // status: 'approved' のみ
    setupSWR(approvedOnly, false);
    render(<AccessRequestsPage />);

    const filterButtons = screen.getAllByRole('button').filter(
      (btn) => btn.className.includes('rounded-full')
    );
    await user.click(filterButtons[1]); // 承認待ちタブ

    expect(screen.getByText('申請がありません')).toBeInTheDocument();
  });
});
