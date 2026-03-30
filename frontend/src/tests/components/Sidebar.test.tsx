import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/Sidebar';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));

import { usePathname } from 'next/navigation';
const mockUsePathname = vi.mocked(usePathname);

const expectedNavItems = [
  { href: '/', label: 'ダッシュボード' },
  { href: '/users', label: 'ユーザ管理' },
  { href: '/access-requests', label: 'アクセス申請' },
  { href: '/audit', label: '監査ログ' },
  { href: '/workflows', label: 'ワークフロー' },
  { href: '/risks', label: 'リスク監視' },
  { href: '/settings', label: '設定' },
];

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePathname.mockReturnValue('/');
  });

  it('全7つのナビゲーションリンクが表示される', () => {
    render(<Sidebar />);
    for (const item of expectedNavItems) {
      expect(screen.getByText(item.label)).toBeInTheDocument();
    }
  });

  it('各リンクの href が正しい', () => {
    render(<Sidebar />);
    for (const item of expectedNavItems) {
      const link = screen.getByText(item.label).closest('a');
      expect(link).toHaveAttribute('href', item.href);
    }
  });

  it('アクティブなリンクにアクティブスタイルが適用される', () => {
    mockUsePathname.mockReturnValue('/users');
    render(<Sidebar />);

    const activeLink = screen.getByText('ユーザ管理').closest('a');
    expect(activeLink?.className).toContain('bg-brand-600/20');
    expect(activeLink?.className).toContain('text-brand-400');
  });

  it('非アクティブなリンクにデフォルトスタイルが適用される', () => {
    mockUsePathname.mockReturnValue('/users');
    render(<Sidebar />);

    const inactiveLink = screen.getByText('設定').closest('a');
    expect(inactiveLink?.className).toContain('text-gray-400');
    expect(inactiveLink?.className).not.toContain('bg-brand-600/20');
  });

  it('ロゴ「ZeroTrust」と「ID Governance」が表示される', () => {
    render(<Sidebar />);
    expect(screen.getByText('ZeroTrust')).toBeInTheDocument();
    expect(screen.getByText('ID Governance')).toBeInTheDocument();
  });

  it('フッター「みらい建設工業」が表示される', () => {
    render(<Sidebar />);
    expect(screen.getByText(/みらい建設工業/)).toBeInTheDocument();
  });
});
