/**
 * Dashboard ルートグループ ローディング UI
 * Next.js App Router のストリーミング機能を活用し、
 * Server Component のデータ取得中に即座にスケルトン UI を表示する。
 *
 * 準拠: ISO27001:2022 A.8.2 可用性制御（ローディング状態の明示）
 */

export default function DashboardLoading() {
  return (
    <div className="p-8 space-y-8 animate-pulse">
      {/* ページヘッダースケルトン */}
      <div className="space-y-2">
        <div className="h-8 w-64 bg-gray-800 rounded" />
        <div className="h-4 w-96 bg-gray-800 rounded" />
      </div>

      {/* KPI カードスケルトン */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-4 w-24 bg-gray-800 rounded" />
              <div className="h-8 w-8 bg-gray-800 rounded-lg" />
            </div>
            <div className="h-8 w-16 bg-gray-800 rounded" />
          </div>
        ))}
      </div>

      {/* セクションタイトルスケルトン */}
      <div className="h-6 w-48 bg-gray-800 rounded" />

      {/* システムステータスグリッドスケルトン */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-4">
            <div className="h-10 w-10 bg-gray-800 rounded-full" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-32 bg-gray-800 rounded" />
              <div className="h-3 w-16 bg-gray-800 rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* 下段コンテンツスケルトン */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="space-y-3">
            <div className="h-6 w-36 bg-gray-800 rounded" />
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-3">
              {[...Array(5)].map((_, j) => (
                <div key={j} className="h-10 bg-gray-800 rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
