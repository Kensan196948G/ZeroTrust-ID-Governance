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

  it('fetcher が fetch して r.json() の結果を返す（line 13）', async () => {
    let capturedFetcher: ((url: string) => Promise<unknown>) | undefined;
    mockUseSWR.mockImplementation((_key, fn) => {
      capturedFetcher = fn as (url: string) => Promise<unknown>;
      return { data: undefined, isLoading: false, error: undefined } as ReturnType<typeof useSWR>;
    });

    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ status: 'ok' }),
    } as Response);

    render(<SystemStatusGrid />);

    expect(capturedFetcher).toBeDefined();
    const result = await capturedFetcher!('/api/v1/health');
    expect(result).toEqual({ status: 'ok' });
  });
});
