'use client';

import useSWR from 'swr';
import { Shield, UserCheck, UserX, Search } from 'lucide-react';
import { useState } from 'react';
import { RiskBadge } from '@/components/RiskBadge';
import type { User } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json()).then((j) => j.data);

export default function UsersPage() {
  const { data: users, isLoading } = useSWR<User[]>('/api/v1/users', fetcher, {
    refreshInterval: 30_000,
  });
  const [search, setSearch] = useState('');

  const filtered = users?.filter(
    (u) =>
      u.display_name.includes(search) ||
      u.email.includes(search) ||
      u.username.includes(search) ||
      u.employee_id.includes(search)
  );

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">ユーザ管理</h1>
          <p className="text-gray-400 text-sm mt-1">
            {users?.length ?? 0} 名のユーザが登録されています
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <UserCheck className="w-4 h-4" />
          新規ユーザ追加
        </button>
      </div>

      {/* 検索 */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          placeholder="名前・メール・社員番号で検索..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5
                     text-sm text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* テーブル */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  ユーザ
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  部署 / 役職
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  ステータス
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  MFA
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  リスクスコア
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  外部システム
                </th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(7)].map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <div className="h-4 bg-gray-800 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500 text-sm">
                    ユーザが見つかりません
                  </td>
                </tr>
              ) : (
                filtered?.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <p className="text-sm font-medium text-white">{user.display_name}</p>
                        <p className="text-xs text-gray-400">{user.email}</p>
                        <p className="text-xs text-gray-600">#{user.employee_id}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm text-gray-300">{user.department ?? '—'}</p>
                      <p className="text-xs text-gray-500">{user.job_title ?? '—'}</p>
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="badge-active">有効</span>
                      ) : (
                        <span className="badge-inactive">無効</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.mfa_enabled ? (
                        <span className="badge-active">
                          <Shield className="w-3 h-3 mr-1" />有効
                        </span>
                      ) : (
                        <span className="badge-danger">
                          <Shield className="w-3 h-3 mr-1" />未設定
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <RiskBadge score={user.risk_score} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-1">
                        <span
                          className={`w-2 h-2 rounded-full ${user.entra_object_id ? 'bg-blue-400' : 'bg-gray-700'}`}
                          title="Entra ID"
                        />
                        <span
                          className={`w-2 h-2 rounded-full ${user.ad_dn ? 'bg-purple-400' : 'bg-gray-700'}`}
                          title="Active Directory"
                        />
                        <span
                          className={`w-2 h-2 rounded-full ${user.hengeone_id ? 'bg-orange-400' : 'bg-gray-700'}`}
                          title="HENGEONE"
                        />
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button className="text-xs text-brand-400 hover:text-brand-300">
                        詳細
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
