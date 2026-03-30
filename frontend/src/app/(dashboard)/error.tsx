'use client';

/**
 * Dashboard ルートグループ エラーバウンダリ
 * クライアントサイドのレンダリングエラーを捕捉し、
 * ユーザーフレンドリーなエラー画面と回復手段を提供する。
 *
 * 準拠: ISO27001:2022 A.8.2 可用性制御（障害時の回復性）
 */

import { useEffect } from 'react';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function DashboardError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // エラーをログに記録（本番では外部監視サービスに送信）
    console.error('Dashboard error:', error);
  }, [error]);

  return (
    <div className="p-8 flex items-center justify-center min-h-[60vh]">
      <div className="bg-gray-900 border border-red-800 rounded-xl p-8 max-w-lg w-full text-center space-y-6">
        {/* エラーアイコン */}
        <div className="flex justify-center">
          <div className="h-16 w-16 bg-red-900/30 rounded-full flex items-center justify-center">
            <span className="text-3xl">⚠️</span>
          </div>
        </div>

        {/* エラーメッセージ */}
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white">
            ページの読み込みに失敗しました
          </h2>
          <p className="text-gray-400 text-sm">
            データの取得中にエラーが発生しました。
            ネットワーク接続を確認してから再試行してください。
          </p>
          {error.digest && (
            <p className="text-gray-600 text-xs font-mono">
              エラーコード: {error.digest}
            </p>
          )}
        </div>

        {/* 回復アクション */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={reset}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            再試行
          </button>
          <button
            onClick={() => window.location.href = '/dashboard'}
            className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            ダッシュボードに戻る
          </button>
        </div>
      </div>
    </div>
  );
}
