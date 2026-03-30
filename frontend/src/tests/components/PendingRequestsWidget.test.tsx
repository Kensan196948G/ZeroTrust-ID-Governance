import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PendingRequestsWidget } from '@/components/PendingRequestsWidget';
import type { AccessRequest } from '@/lib/api';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

import useSWR from 'swr';
const mockUseSWR = vi.mocked(useSWR);

vi.mock('@/lib/api', () => ({
  accessApi: {
    pending: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

import { accessApi } from '@/lib/api';

const mockRequests: AccessRequest[] = [
  {
    id: 'req-001',
    request_type: 'role_assignment',
    justification: 'プロジェクトAへのアクセスが必要です',
    status: 'pending',
    created_at: new Date(Date.now() - 300_000).toISOString(),
    expires_at: null,
  },
  {
    id: 'req-002',
    request_type: 'privilege_escalation',
    justification: '管理者権限が一時的に必要です',
    status: 'pending',
    created_at: new Date(Date.now() - 600_000).toISOString(),
    expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  },
];

describe('PendingRequestsWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ローディング中にスケルトンが表示される', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    const { container } = render(<PendingRequestsWidget />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons).toHaveLength(3);
  });

  it('データなし時に空メッセージが表示される', () => {
    mockUseSWR.mockReturnValue({
      data: [],
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<PendingRequestsWidget />);
    expect(screen.getByText('承認待ちの申請はありません')).toBeInTheDocument();
  });

  it('データあり時に申請一覧が表示される', () => {
    mockUseSWR.mockReturnValue({
      data: mockRequests,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<PendingRequestsWidget />);
    // 承認・却下ボタンが各申請に2つずつ表示される
    const approveButtons = screen.getAllByText('承認');
    const rejectButtons = screen.getAllByText('却下');
    expect(approveButtons).toHaveLength(2);
    expect(rejectButtons).toHaveLength(2);
  });

  it('申請のrequest_typeとjustificationが表示される', () => {
    mockUseSWR.mockReturnValue({
      data: mockRequests,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<PendingRequestsWidget />);
    expect(screen.getByText('role_assignment 申請')).toBeInTheDocument();
    expect(screen.getByText('プロジェクトAへのアクセスが必要です')).toBeInTheDocument();
    expect(screen.getByText('privilege_escalation 申請')).toBeInTheDocument();
    expect(screen.getByText('管理者権限が一時的に必要です')).toBeInTheDocument();
  });

  it('承認ボタンクリックで accessApi.approve が呼ばれる', async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn();

    mockUseSWR.mockReturnValue({
      data: [mockRequests[0]],
      isLoading: false,
      error: undefined,
      mutate: mockMutate,
    } as unknown as ReturnType<typeof useSWR>);

    vi.mocked(accessApi.approve).mockResolvedValue(undefined as never);

    render(<PendingRequestsWidget />);
    await user.click(screen.getByText('承認'));

    expect(accessApi.approve).toHaveBeenCalledWith('req-001');
  });

  it('却下ボタンクリックで accessApi.reject が呼ばれる', async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn();

    mockUseSWR.mockReturnValue({
      data: [mockRequests[0]],
      isLoading: false,
      error: undefined,
      mutate: mockMutate,
    } as unknown as ReturnType<typeof useSWR>);

    vi.mocked(accessApi.reject).mockResolvedValue(undefined as never);

    render(<PendingRequestsWidget />);
    await user.click(screen.getByText('却下'));

    expect(accessApi.reject).toHaveBeenCalledWith('req-001');
  });

  it('アクション成功後に mutate が呼ばれる', async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn();

    mockUseSWR.mockReturnValue({
      data: [mockRequests[0]],
      isLoading: false,
      error: undefined,
      mutate: mockMutate,
    } as unknown as ReturnType<typeof useSWR>);

    vi.mocked(accessApi.approve).mockResolvedValue(undefined as never);

    render(<PendingRequestsWidget />);
    await user.click(screen.getByText('承認'));

    expect(mockMutate).toHaveBeenCalled();
  });

  it('アクション失敗時に console.error が出力される', async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    mockUseSWR.mockReturnValue({
      data: [mockRequests[0]],
      isLoading: false,
      error: undefined,
      mutate: mockMutate,
    } as unknown as ReturnType<typeof useSWR>);

    vi.mocked(accessApi.approve).mockRejectedValue(new Error('Network error'));

    render(<PendingRequestsWidget />);
    await user.click(screen.getByText('承認'));

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      '申請の承認に失敗しました:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });
});
