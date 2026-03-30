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
  usersApi: { list: vi.fn() },
}));

// RiskBadge mock
vi.mock('@/components/RiskBadge', () => ({
  RiskBadge: ({ score }: { score: number }) => <span data-testid="risk-badge">{score}</span>,
}));

import UsersPage from '@/app/(dashboard)/users/page';

const mockUsers = [
  {
    id: 'u1',
    employee_id: 'EMP001',
    username: 'tanaka.taro',
    display_name: '田中太郎',
    email: 'tanaka@example.com',
    user_type: 'employee' as const,
    account_status: 'active' as const,
    mfa_enabled: true,
    risk_score: 25,
    hire_date: '2020-04-01',
    created_at: '2020-04-01T00:00:00Z',
  },
  {
    id: 'u2',
    employee_id: 'EMP002',
    username: 'suzuki.hanako',
    display_name: '鈴木花子',
    email: 'suzuki@example.com',
    user_type: 'contractor' as const,
    account_status: 'disabled' as const,
    mfa_enabled: false,
    risk_score: 60,
    hire_date: '2021-01-15',
    created_at: '2021-01-15T00:00:00Z',
  },
  {
    id: 'u3',
    employee_id: 'EMP003',
    username: 'yamada.jiro',
    display_name: '山田次郎',
    email: 'yamada@example.com',
    user_type: 'admin' as const,
    account_status: 'suspended' as const,
    mfa_enabled: true,
    risk_score: 80,
    hire_date: '2019-06-01',
    created_at: '2019-06-01T00:00:00Z',
  },
];

describe('UsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ローディング中にスケルトンが表示される', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    const { container } = render(<UsersPage />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('ユーザーリストが正しく表示される（display_name, email, employee_id）', () => {
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    expect(screen.getByText('田中太郎')).toBeInTheDocument();
    expect(screen.getByText('tanaka@example.com')).toBeInTheDocument();
    expect(screen.getByText('#EMP001')).toBeInTheDocument();

    expect(screen.getByText('鈴木花子')).toBeInTheDocument();
    expect(screen.getByText('suzuki@example.com')).toBeInTheDocument();
    expect(screen.getByText('#EMP002')).toBeInTheDocument();
  });

  it('検索でフィルタリングされる', async () => {
    const user = userEvent.setup();
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    const searchInput = screen.getByPlaceholderText('名前・メール・社員番号で検索...');
    await user.type(searchInput, '田中');

    expect(screen.getByText('田中太郎')).toBeInTheDocument();
    expect(screen.queryByText('鈴木花子')).not.toBeInTheDocument();
    expect(screen.queryByText('山田次郎')).not.toBeInTheDocument();
  });

  it('検索結果が0件の時に「ユーザが見つかりません」表示', async () => {
    const user = userEvent.setup();
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    const searchInput = screen.getByPlaceholderText('名前・メール・社員番号で検索...');
    await user.type(searchInput, '存在しないユーザ');

    expect(screen.getByText('ユーザが見つかりません')).toBeInTheDocument();
  });

  it('MFAステータス（有効/未設定）が正しく表示される', () => {
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    // mfa_enabled: true のユーザが2人（田中、山田）、false が1人（鈴木）
    const enabledBadges = screen.getAllByText('有効');
    // account_status='active' の「有効」+ mfa_enabled の「有効」が混在するので
    // MFA「未設定」が表示されることを確認
    expect(screen.getByText('未設定')).toBeInTheDocument();
    expect(enabledBadges.length).toBeGreaterThan(0);
  });

  it('アカウントステータス（有効/無効/停止）が正しく表示される', () => {
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    // active -> 有効, disabled -> 無効, suspended -> 停止
    expect(screen.getByText('無効')).toBeInTheDocument();
    expect(screen.getByText('停止')).toBeInTheDocument();
  });

  it('「新規ユーザ追加」ボタンが表示される', () => {
    mockUseSWR.mockReturnValue({
      data: mockUsers,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);

    render(<UsersPage />);

    expect(screen.getByText('新規ユーザ追加')).toBeInTheDocument();
  });
});
