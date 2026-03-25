'use client';

import useSWR from 'swr';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';
import { auditApi, type AuditLog } from '@/lib/api';

export function RecentAuditLogs() {
  const { data: logs, isLoading } = useSWR<AuditLog[]>(
    'recent-audit-logs',
    () => auditApi.list({ per_page: 8 }),
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
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              {log.event_type} / {log.source_system}
              {log.actor_user_id && ` — ${log.actor_user_id.slice(0, 8)}…`}
            </p>
          </div>
          <time className="text-xs text-gray-500 whitespace-nowrap flex-shrink-0">
            {formatDistanceToNow(new Date(log.event_time), { locale: ja, addSuffix: true })}
          </time>
        </div>
      ))}
    </div>
  );
}
