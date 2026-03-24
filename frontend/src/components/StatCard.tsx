import clsx from 'clsx';
import type { LucideIcon } from 'lucide-react';

type Props = {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  variant?: 'default' | 'danger' | 'warning' | 'success';
};

export function StatCard({ title, value, icon: Icon, trend, variant = 'default' }: Props) {
  return (
    <div
      className={clsx(
        'card relative overflow-hidden',
        variant === 'danger' && 'border-red-800/50',
        variant === 'warning' && 'border-yellow-800/50',
        variant === 'success' && 'border-green-800/50'
      )}
    >
      {/* 背景グラデーション */}
      <div
        className={clsx(
          'absolute inset-0 opacity-5',
          variant === 'danger' && 'bg-gradient-to-br from-red-500',
          variant === 'warning' && 'bg-gradient-to-br from-yellow-500',
          variant === 'success' && 'bg-gradient-to-br from-green-500',
          variant === 'default' && 'bg-gradient-to-br from-blue-500'
        )}
      />

      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
          {trend && (
            <p
              className={clsx(
                'text-xs mt-1',
                trend.value > 0 ? 'text-red-400' : 'text-green-400'
              )}
            >
              {trend.value > 0 ? '▲' : '▼'} {Math.abs(trend.value)}% {trend.label}
            </p>
          )}
        </div>
        <div
          className={clsx(
            'p-3 rounded-xl',
            variant === 'danger' && 'bg-red-900/30 text-red-400',
            variant === 'warning' && 'bg-yellow-900/30 text-yellow-400',
            variant === 'success' && 'bg-green-900/30 text-green-400',
            variant === 'default' && 'bg-brand-900/30 text-brand-400'
          )}
        >
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}
