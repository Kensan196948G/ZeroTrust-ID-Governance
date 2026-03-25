import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RecentAuditLogs } from '@/components/RecentAuditLogs';
import type { AuditLog } from '@/lib/api';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

import useSWR from 'swr';
const mockUseSWR = vi.mocked(useSWR);

const mockLogs: AuditLog[] = [
  {
    id: 1,
    event_id: 'evt-001',
    event_time: new Date(Date.now() - 60_000).toISOString(), // 1分前
    event_type: 'LOGIN',
    source_system: 'EntraID',
    actor_user_id: 'user-abc-12345',
    action: 'user.login.success',
    result: 'success',
    risk_score: 10,
  },
  {
    id: 2,
    event_id: 'evt-002',
    event_time: new Date(Date.now() - 120_000).toISOString(), // 2分前
    event_type: 'ACCESS_REQUEST',
    source_system: 'HENGEONE',
    actor_user_id: null,
    action: 'access.request.created',
    result: 'success',
    risk_score: null,
  },
];

describe('RecentAuditLogs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ローディング中はスケルトンを表示する', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    const { container } = render(<RecentAuditLogs />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('ログが空のとき「監査ログがありません」を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: [],
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<RecentAuditLogs />);
    expect(screen.getByText('監査ログがありません')).toBeInTheDocument();
  });

  it('ログデータがあるときアクションを表示する', () => {
    mockUseSWR.mockReturnValue({
      data: mockLogs,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<RecentAuditLogs />);
    expect(screen.getByText('user.login.success')).toBeInTheDocument();
    expect(screen.getByText('access.request.created')).toBeInTheDocument();
  });

  it('event_type と source_system を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: mockLogs,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<RecentAuditLogs />);
    expect(screen.getByText(/LOGIN.*EntraID/)).toBeInTheDocument();
    expect(screen.getByText(/ACCESS_REQUEST.*HENGEONE/)).toBeInTheDocument();
  });

  it('actor_user_id がある場合は先頭8文字＋…を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: [mockLogs[0]],
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<RecentAuditLogs />);
    // actor_user_id = 'user-abc-12345' → 先頭8文字 'user-abc' + '…'
    expect(screen.getByText(/user-abc…/)).toBeInTheDocument();
  });

  it('actor_user_id が null の場合はユーザーIDを表示しない', () => {
    mockUseSWR.mockReturnValue({
      data: [mockLogs[1]],
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<RecentAuditLogs />);
    expect(screen.queryByText(/…/)).not.toBeInTheDocument();
  });
});
