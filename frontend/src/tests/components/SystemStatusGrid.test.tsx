import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SystemStatusGrid } from '@/components/SystemStatusGrid';

// useSWR をモック化してネットワーク通信なしにテスト
vi.mock('swr', () => ({
  default: vi.fn(),
}));

import useSWR from 'swr';
const mockUseSWR = vi.mocked(useSWR);

describe('SystemStatusGrid', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('3つのシステム名を常に表示する', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<SystemStatusGrid />);
    expect(screen.getByText('Microsoft Entra ID')).toBeInTheDocument();
    expect(screen.getByText('Active Directory')).toBeInTheDocument();
    expect(screen.getByText('HENGEONE')).toBeInTheDocument();
  });

  it('ローディング中は「確認中...」を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<SystemStatusGrid />);
    const loadingElements = screen.getAllByText('確認中...');
    expect(loadingElements).toHaveLength(3);
  });

  it('status=ok のとき「接続中」を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: { status: 'ok' },
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<SystemStatusGrid />);
    const onlineElements = screen.getAllByText('接続中');
    expect(onlineElements).toHaveLength(3);
  });

  it('status≠ok のとき「未接続」を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: { status: 'error' },
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<SystemStatusGrid />);
    const offlineElements = screen.getAllByText('未接続');
    expect(offlineElements).toHaveLength(3);
  });

  it('データなし（undefined）のとき「未接続」を表示する', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: undefined,
    } as ReturnType<typeof useSWR>);

    render(<SystemStatusGrid />);
    const offlineElements = screen.getAllByText('未接続');
    expect(offlineElements).toHaveLength(3);
  });
});
