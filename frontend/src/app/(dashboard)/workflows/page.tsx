'use client';

import useSWR from 'swr';
import { useState } from 'react';
import { Play, RefreshCw, AlertTriangle, CheckCircle2, Clock, Zap } from 'lucide-react';
import { workflowsApi } from '@/lib/api';

const healthFetcher = (url: string) => fetch(url).then((r) => r.json());

// ワークフロー定義
type WorkflowTrigger = () => Promise<{ task_id: string; status: string }>;

const WORKFLOWS: {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  trigger: WorkflowTrigger;
  schedule: string;
}[] = [
  {
    id: 'quarterly-review',
    name: '四半期アクセス棚卸',
    description: 'ILM-005: 全ユーザーの3システム整合性チェック・SoD違反検出・期限切れロール削除',
    icon: '🔍',
    category: 'ILM',
    trigger: workflowsApi.quarterlyReview,
    schedule: '毎四半期（90日ごと）',
  },
  {
    id: 'consistency-check',
    name: '整合性チェック',
    description: '3システム間のユーザー情報乖離を検出し、不整合レポートを生成',
    icon: '⚖️',
    category: 'ILM',
    trigger: workflowsApi.consistencyCheck,
    schedule: '毎日 00:00',
  },
  {
    id: 'risk-scan',
    name: 'リスクスキャン',
    description: '全ユーザーのリスクスコアを再計算し、高リスクユーザーに警告',
    icon: '🎯',
    category: 'Security',
    trigger: workflowsApi.riskScan,
    schedule: '毎時',
  },
  {
    id: 'pim-expiry',
    name: 'PIM 期限切れ処理',
    description: '期限切れ特権アクセス（時限付きロール）を自動的に剥奪',
    icon: '⏱️',
    category: 'PIM',
    trigger: workflowsApi.pimExpiry,
    schedule: '30分ごと',
  },
  {
    id: 'mfa-enforcement',
    name: 'MFA 未設定アカウント対応',
    description: 'MFA未設定かつリスクスコア30以上のアカウントを自動停止',
    icon: '🔐',
    category: 'Security',
    trigger: workflowsApi.mfaEnforcement,
    schedule: '毎日 09:00',
  },
];

const CATEGORY_COLORS: Record<string, string> = {
  ILM:      'bg-blue-900/30 text-blue-300 border border-blue-700/40',
  Security: 'bg-red-900/30 text-red-300 border border-red-700/40',
  PIM:      'bg-purple-900/30 text-purple-300 border border-purple-700/40',
};

export default function WorkflowsPage() {
  const [runningWorkflows, setRunningWorkflows] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<Record<string, { success: boolean; message: string }>>({});

  const { data: health } = useSWR('/api/v1/health', healthFetcher, { refreshInterval: 30_000 });
  const isSystemOnline = health?.status === 'ok';

  async function triggerWorkflow(wf: typeof WORKFLOWS[number]) {
    if (runningWorkflows.has(wf.id)) return;

    setRunningWorkflows((prev) => new Set([...prev, wf.id]));
    try {
      const data = await wf.trigger();
      setResults((prev) => ({
        ...prev,
        [wf.id]: {
          success: true,
          message: `タスクID: ${data.task_id} — ${data.status}`,
        },
      }));
    } catch (err) {
      setResults((prev) => ({
        ...prev,
        [wf.id]: {
          success: false,
          message: err instanceof Error ? err.message : 'エラーが発生しました',
        },
      }));
    } finally {
      setRunningWorkflows((prev) => {
        const next = new Set(prev);
        next.delete(wf.id);
        return next;
      });
    }
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-400" />
            ワークフロー管理
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            ILM・セキュリティ・PIM の自動化タスクを手動実行・スケジュール管理
          </p>
        </div>
        <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-full ${
          isSystemOnline
            ? 'bg-green-900/30 text-green-400 border border-green-700/40'
            : 'bg-gray-800 text-gray-500'
        }`}>
          <span className={`w-2 h-2 rounded-full ${isSystemOnline ? 'bg-green-400' : 'bg-gray-600'}`} />
          {isSystemOnline ? 'システム稼働中' : '確認中...'}
        </div>
      </div>

      {/* ワークフローグリッド */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {WORKFLOWS.map((wf) => {
          const isRunning = runningWorkflows.has(wf.id);
          const result = results[wf.id];

          return (
            <div key={wf.id} className="card space-y-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{wf.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-white">{wf.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${CATEGORY_COLORS[wf.category] ?? ''}`}>
                      {wf.category}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{wf.description}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                スケジュール: {wf.schedule}
              </div>

              {/* 実行結果 */}
              {result && (
                <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${
                  result.success
                    ? 'bg-green-900/20 text-green-400'
                    : 'bg-red-900/20 text-red-400'
                }`}>
                  {result.success ? (
                    <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                  )}
                  {result.message}
                </div>
              )}

              {/* 実行ボタン */}
              <button
                onClick={() => triggerWorkflow(wf)}
                disabled={isRunning || !isSystemOnline}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg
                           bg-brand-600/20 text-brand-400 border border-brand-600/30 text-sm
                           hover:bg-brand-600/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    実行中...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    手動実行
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* 注意書き */}
      <div className="flex items-start gap-3 p-4 bg-yellow-900/10 border border-yellow-700/30 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-yellow-300/80">
          手動実行は本番データに影響します。実行前に承認者への確認を推奨します。
          実行結果はすべて監査ログに記録されます（AUD-001）。
        </p>
      </div>
    </div>
  );
}
