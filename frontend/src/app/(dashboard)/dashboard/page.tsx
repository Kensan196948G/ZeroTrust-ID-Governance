/**
 * ダッシュボード画面（Server Component）
 * IDガバナンスの全体状況を一目で把握できる
 */

import { Users, ShieldAlert, ClipboardCheck, Activity } from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { SystemStatusGrid } from '@/components/SystemStatusGrid';
import { RecentAuditLogs } from '@/components/RecentAuditLogs';
import { PendingRequestsWidget } from '@/components/PendingRequestsWidget';

// サーバーコンポーネントで統計データを取得
async function getDashboardStats() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';
  try {
    const [usersRes, pendingRes] = await Promise.allSettled([
      fetch(`${apiBase}/api/v1/users`, { next: { revalidate: 30 } }),
      fetch(`${apiBase}/api/v1/access-requests/pending`, { next: { revalidate: 30 } }),
    ]);

    const users = usersRes.status === 'fulfilled' && usersRes.value.ok
      ? (await usersRes.value.json()).data
      : [];
    const pending = pendingRes.status === 'fulfilled' && pendingRes.value.ok
      ? (await pendingRes.value.json()).data
      : [];

    const activeUsers = users.filter((u: { account_status: string }) => u.account_status === 'active').length;
    const highRiskUsers = users.filter((u: { risk_score: number }) => u.risk_score >= 70).length;
    const mfaEnabled = users.filter((u: { mfa_enabled: boolean }) => u.mfa_enabled).length;
    const mfaRate = users.length > 0 ? Math.round((mfaEnabled / users.length) * 100) : 0;

    return {
      totalUsers: users.length,
      activeUsers,
      highRiskUsers,
      pendingApprovals: pending.length,
      mfaRate,
    };
  } catch {
    return {
      totalUsers: 0,
      activeUsers: 0,
      highRiskUsers: 0,
      pendingApprovals: 0,
      mfaRate: 0,
    };
  }
}

export default async function DashboardPage() {
  const stats = await getDashboardStats();

  return (
    <div className="p-8 space-y-8">
      {/* ページヘッダー */}
      <div>
        <h1 className="text-2xl font-bold text-white">IDガバナンス ダッシュボード</h1>
        <p className="text-gray-400 text-sm mt-1">
          ゼロトラスト アイデンティティ管理の全体状況
        </p>
      </div>

      {/* KPI カード */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="総ユーザ数"
          value={stats.totalUsers}
          icon={Users}
          variant="default"
        />
        <StatCard
          title="高リスクユーザ"
          value={stats.highRiskUsers}
          icon={ShieldAlert}
          variant={stats.highRiskUsers > 0 ? 'danger' : 'success'}
        />
        <StatCard
          title="承認待ち申請"
          value={stats.pendingApprovals}
          icon={ClipboardCheck}
          variant={stats.pendingApprovals > 5 ? 'warning' : 'default'}
        />
        <StatCard
          title="MFA 有効率"
          value={`${stats.mfaRate}%`}
          icon={Activity}
          variant={stats.mfaRate < 80 ? 'warning' : 'success'}
        />
      </div>

      {/* 外部システム連携状態 */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">
          🔗 外部システム接続状態
        </h2>
        <SystemStatusGrid />
      </div>

      {/* 下段: 監査ログ + 承認待ち */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">
            📋 最近の監査ログ
          </h2>
          <RecentAuditLogs />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">
            ⏳ 承認待ちアクセス申請
          </h2>
          <PendingRequestsWidget />
        </div>
      </div>
    </div>
  );
}
