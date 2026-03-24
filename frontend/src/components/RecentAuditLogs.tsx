'use client';

import useSWR from 'swr';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';
import type { AuditLog } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json()).then((j) => j.data);

export function RecentAuditLogs() {
  const { data: logs, isLoading } = useSWR<AuditLog[]>(
    '/api/v1/audit-logs?limit=8',
    fetcher,
    { refreshInterval: 15_000 }
  );

  if (isLoading) {
    return (
      <div className="card space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (!logs?.length) {
    return (
      <div className="card text-center py-8 text-gray-500 text-sm">
        監査ログがありません
      </div>
    );
  }

  return (
    <div className="card divide-y divide-gray-800">
      {logs.map((log) => (
        <div key={log.id} className="py-3 flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-mono text-gray-200 truncate">{log.action}</p>
            {log.actor_id && (
              <p className="text-xs text-gray-500 mt-0.5 truncate">
                Actor: {log.actor_id}
              </p>
            )}
          </div>
          <time className="text-xs text-gray-500 whitespace-nowrap flex-shrink-0">
            {formatDistanceToNow(new Date(log.created_at), { locale: ja, addSuffix: true })}
          </time>
        </div>
      ))}
    </div>
  );
}
