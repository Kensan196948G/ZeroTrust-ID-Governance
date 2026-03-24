'use client';

import useSWR from 'swr';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';
import type { AccessRequest } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json()).then((j) => j.data);

export function PendingRequestsWidget() {
  const { data: requests, isLoading, mutate } = useSWR<AccessRequest[]>(
    '/api/v1/access-requests/pending',
    fetcher,
    { refreshInterval: 15_000 }
  );

  async function handleAction(id: string, action: 'approve' | 'reject') {
    // デモ用 approver ID
    const approverId = '00000000-0000-0000-0000-000000000001';
    await fetch(`/api/v1/access-requests/${id}?action=${action}&approver_id=${approverId}`, {
      method: 'PATCH',
    });
    mutate();
  }

  if (isLoading) {
    return (
      <div className="card space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-800 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (!requests?.length) {
    return (
      <div className="card text-center py-8 text-gray-500 text-sm">
        <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
        承認待ちの申請はありません
      </div>
    );
  }

  return (
    <div className="card divide-y divide-gray-800">
      {requests.map((req) => (
        <div key={req.id} className="py-4">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white capitalize">{req.request_type} 申請</p>
              <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{req.justification}</p>
            </div>
            <time className="text-xs text-gray-500 whitespace-nowrap flex-shrink-0">
              {formatDistanceToNow(new Date(req.created_at), { locale: ja, addSuffix: true })}
            </time>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleAction(req.id, 'approve')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-900/30
                         text-green-400 border border-green-800/50 text-xs font-medium
                         hover:bg-green-900/50 transition-colors"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              承認
            </button>
            <button
              onClick={() => handleAction(req.id, 'reject')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-900/30
                         text-red-400 border border-red-800/50 text-xs font-medium
                         hover:bg-red-900/50 transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" />
              却下
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
