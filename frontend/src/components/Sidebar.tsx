'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Shield,
  Users,
  ClipboardList,
  FileText,
  Activity,
  Settings,
  BarChart3,
  AlertTriangle,
} from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { href: '/', label: 'ダッシュボード', icon: BarChart3 },
  { href: '/users', label: 'ユーザ管理', icon: Users },
  { href: '/access-requests', label: 'アクセス申請', icon: ClipboardList },
  { href: '/audit', label: '監査ログ', icon: FileText },
  { href: '/workflows', label: 'ワークフロー', icon: Activity },
  { href: '/risks', label: 'リスク監視', icon: AlertTriangle },
  { href: '/settings', label: '設定', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col min-h-screen">
      {/* ロゴ */}
      <div className="p-6 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-brand-600 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-tight">ZeroTrust</p>
            <p className="text-xs text-gray-400 leading-tight">ID Governance</p>
          </div>
        </div>
      </div>

      {/* ナビゲーション */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== '/' && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* フッター */}
      <div className="p-4 border-t border-gray-800">
        <p className="text-xs text-gray-600">
          みらい建設工業<br />
          ISO 27001 / NIST CSF 準拠
        </p>
      </div>
    </aside>
  );
}
