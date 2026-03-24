'use client';

import useSWR from 'swr';
import { useState } from 'react';
import { CheckCircle2, XCircle, Clock, PlusCircle, Filter } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';
import type { AccessRequest } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json()).then((j) => j.data);

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  pending:  { label: '承認待ち', className: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/50' },
  approved: { label: '承認済み', className: 'bg-green-900/40 text-green-300 border border-green-700/50' },
  rejected: { label: '却下',     className: 'bg-red-900/40 text-red-300 border border-red-700/50' },
};

const TYPE_LABELS: Record<string, string> = {
  grant:    'アクセス付与',
  revoke:   'アクセス剥奪',
  transfer: '権限移譲',
  review:   '棚卸',
};

export default function AccessRequestsPage() {
  const { data: requests, isLoading, mutate } = useSWR<AccessRequest[]>(
    '/api/v1/access-requests',
    fetcher,
    { refreshInterval: 15_000 }
  );
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');

  const filtered = requests?.filter((r) => filter === 'all' || r.status === filter);

  async function handleAction(id: string, action: 'approve' | 'reject') {
    const approverId = '00000000-0000-0000-0000-000000000001';
    await fetch(`/api/v1/access-requests/${id}?action=${action}&approver_id=${approverId}`, {
      method: 'PATCH',
    });
    mutate();
  }

  const counts = {
    all:      requests?.length ?? 0,
    pending:  requests?.filter((r) => r.status === 'pending').length ?? 0,
    approved: requests?.filter((r) => r.status === 'approved').length ?? 0,
    rejected: requests?.filter((r) => r.status === 'rejected').length ?? 0,
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">アクセス申請管理</h1>
          <p className="text-gray-400 text-sm mt-1">GOV-003 セルフサービスポータル</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <PlusCircle className="w-4 h-4" />
          新規申請
        </button>
      </div>

      {/* フィルタータブ */}
      <div className="flex gap-2 border-b border-gray-800 pb-4">
        {(['all', 'pending', 'approved', 'rejected'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === s
                ? 'bg-brand-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            {s === 'all' ? 'すべて' : STATUS_LABELS[s]?.label}
            <span className="ml-1.5 text-xs opacity-75">({counts[s]})</span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
          <Filter className="w-3 h-3" /> フィルター
        </div>
      </div>

      {/* 申請一覧 */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  種別
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  申請理由
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  ステータス
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  申請日時
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  有効期限
                </th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(6)].map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <div className="h-4 bg-gray-800 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500 text-sm">
                    <Clock className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    申請がありません
                  </td>
                </tr>
              ) : (
                filtered?.map((req) => (
                  <tr key={req.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <span className="text-sm font-medium text-white capitalize">
                        {TYPE_LABELS[req.request_type] ?? req.request_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-xs">
                      <p className="text-sm text-gray-300 line-clamp-2">{req.justification}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_LABELS[req.status]?.className ?? ''}`}>
                        {STATUS_LABELS[req.status]?.label ?? req.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-gray-500 whitespace-nowrap">
                      {formatDistanceToNow(new Date(req.created_at), { locale: ja, addSuffix: true })}
                    </td>
                    <td className="px-6 py-4 text-xs text-gray-500">
                      {req.expires_at
                        ? formatDistanceToNow(new Date(req.expires_at), { locale: ja, addSuffix: true })
                        : '—'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {req.status === 'pending' && (
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => handleAction(req.id, 'approve')}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-green-900/30
                                       text-green-400 border border-green-800/50 text-xs hover:bg-green-900/50"
                          >
                            <CheckCircle2 className="w-3 h-3" /> 承認
                          </button>
                          <button
                            onClick={() => handleAction(req.id, 'reject')}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-900/30
                                       text-red-400 border border-red-800/50 text-xs hover:bg-red-900/50"
                          >
                            <XCircle className="w-3 h-3" /> 却下
                          </button>
                        </div>
                      )}
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
