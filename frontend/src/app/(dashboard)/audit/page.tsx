'use client';

import useSWR from 'swr';
import { useState } from 'react';
import { Shield, Search, Download } from 'lucide-react';
import { format } from 'date-fns';
import { ja } from 'date-fns/locale';
import type { AuditLog } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json()).then((j) => j.data);

// アクションカテゴリ別の色分け
function actionColor(action: string): string {
  if (action.includes('CREATE') || action.includes('PROVISION')) return 'text-green-400';
  if (action.includes('DELETE') || action.includes('DEPROVISION')) return 'text-red-400';
  if (action.includes('UPDATE') || action.includes('TRANSFER')) return 'text-yellow-400';
  if (action.includes('APPROVE')) return 'text-blue-400';
  if (action.includes('REJECT') || action.includes('BLOCK')) return 'text-red-400';
  return 'text-gray-300';
}

export default function AuditPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data: logs, isLoading } = useSWR<AuditLog[]>(
    `/api/v1/audit-logs?limit=${limit}&offset=${page * limit}`,
    fetcher,
    { refreshInterval: 30_000 }
  );

  const filtered = logs?.filter(
    (l) =>
      l.action.toLowerCase().includes(search.toLowerCase()) ||
      (l.actor_id ?? '').includes(search)
  );

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="w-6 h-6 text-brand-400" />
            監査ログ
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            AUD-001 改ざん防止 SHA256 チェーンハッシュ対応
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2 text-sm">
          <Download className="w-4 h-4" />
          CSV エクスポート
        </button>
      </div>

      {/* 検索 */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          placeholder="アクション・アクターIDで検索..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5
                     text-sm text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* ログテーブル */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  日時
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  アクション
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  アクター
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  対象リソース
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  IP アドレス
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  整合性ハッシュ
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(6)].map((_, j) => (
                      <td key={j} className="px-6 py-3">
                        <div className="h-4 bg-gray-800 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500 text-sm">
                    ログがありません
                  </td>
                </tr>
              ) : (
                filtered?.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-6 py-3 text-xs text-gray-500 whitespace-nowrap font-mono">
                      {format(new Date(log.created_at), 'yyyy/MM/dd HH:mm:ss', { locale: ja })}
                    </td>
                    <td className="px-6 py-3">
                      <span className={`text-xs font-mono font-semibold ${actionColor(log.action)}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-400 font-mono truncate max-w-[140px]">
                      {log.actor_id ?? '—'}
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-400 truncate max-w-[140px]">
                      {(log as any).resource_type ?? '—'}
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-500 font-mono">
                      {(log as any).source_ip ?? '—'}
                    </td>
                    <td className="px-6 py-3">
                      {(log as any).chain_hash ? (
                        <span
                          className="text-xs font-mono text-green-500/70 truncate block max-w-[120px]"
                          title={(log as any).chain_hash}
                        >
                          ✓ {((log as any).chain_hash as string).slice(0, 12)}…
                        </span>
                      ) : (
                        <span className="text-xs text-gray-600">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* ページネーション */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-800">
          <span className="text-xs text-gray-500">
            ページ {page + 1} (各 {limit} 件)
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 text-xs rounded border border-gray-700 text-gray-400
                         disabled:opacity-30 hover:border-gray-500 transition-colors"
            >
              ← 前へ
            </button>
            <button
              disabled={(logs?.length ?? 0) < limit}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 text-xs rounded border border-gray-700 text-gray-400
                         disabled:opacity-30 hover:border-gray-500 transition-colors"
            >
              次へ →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
