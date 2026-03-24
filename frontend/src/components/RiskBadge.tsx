import clsx from 'clsx';

type Props = {
  score: number;
  showLabel?: boolean;
};

export function RiskBadge({ score, showLabel = true }: Props) {
  const level = score >= 70 ? 'high' : score >= 30 ? 'medium' : 'low';
  const label = level === 'high' ? '高リスク' : level === 'medium' ? '中リスク' : '低リスク';

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        level === 'high' && 'bg-red-900/30 text-red-400 border border-red-800/50',
        level === 'medium' && 'bg-yellow-900/30 text-yellow-400 border border-yellow-800/50',
        level === 'low' && 'bg-green-900/30 text-green-400 border border-green-800/50'
      )}
    >
      <span
        className={clsx(
          'w-1.5 h-1.5 rounded-full',
          level === 'high' && 'bg-red-400',
          level === 'medium' && 'bg-yellow-400',
          level === 'low' && 'bg-green-400'
        )}
      />
      {score}
      {showLabel && <span className="text-xs opacity-75">{label}</span>}
    </span>
  );
}
