'use client';

import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import useSWR from 'swr';

const systems = [
  { id: 'entra', name: 'Microsoft Entra ID', icon: '🔵', endpoint: '/health' },
  { id: 'ad', name: 'Active Directory', icon: '🟣', endpoint: '/health' },
  { id: 'hengeone', name: 'HENGEONE', icon: '🟠', endpoint: '/health' },
];

const fetcher = (url: string) =>
  fetch(url).then((r) => r.json());

export function SystemStatusGrid() {
  const { data, isLoading } = useSWR('/api/v1/health', fetcher, {
    refreshInterval: 30_000,
  });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {systems.map((system) => {
        const isOnline = data?.status === 'ok';

        return (
          <div key={system.id} className="card flex items-center gap-4">
            <span className="text-3xl">{system.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{system.name}</p>
              {isLoading ? (
                <div className="flex items-center gap-1 mt-1 text-xs text-gray-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  確認中...
                </div>
              ) : isOnline ? (
                <div className="flex items-center gap-1 mt-1 text-xs text-green-400">
                  <CheckCircle2 className="w-3 h-3" />
                  接続中
                </div>
              ) : (
                <div className="flex items-center gap-1 mt-1 text-xs text-red-400">
                  <XCircle className="w-3 h-3" />
                  未接続
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
