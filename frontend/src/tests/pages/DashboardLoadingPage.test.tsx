/**
 * DashboardLoading コンポーネントテスト（Phase 23）
 *
 * loading.tsx は Next.js App Router のストリーミング機能に使用される
 * スケルトン UI コンポーネント。Server Component データ取得中に表示される。
 *
 * 準拠: ISO27001:2022 A.8.2 テスト制御
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DashboardLoading from '@/app/(dashboard)/loading';

describe('DashboardLoading', () => {
  it('スケルトン UI がレンダリングされる', () => {
    const { container } = render(<DashboardLoading />);
    // animate-pulse クラスがルート要素に適用されている
    const root = container.firstElementChild;
    expect(root).not.toBeNull();
    expect(root?.className).toContain('animate-pulse');
  });

  it('KPI カードスケルトンが4枚表示される', () => {
    const { container } = render(<DashboardLoading />);
    // KPI カードは bg-gray-900 border border-gray-800 rounded-xl p-6
    const cards = container.querySelectorAll('.bg-gray-900.border.rounded-xl');
    // 最低 4 枚（KPI 4 枚 + システム 3 枚 + 下段 2 枚 = 9 枚以上）
    expect(cards.length).toBeGreaterThanOrEqual(4);
  });

  it('システムステータスグリッドスケルトンが3枚表示される', () => {
    const { container } = render(<DashboardLoading />);
    // grid cols-3 のシステムカード
    const systemSection = container.querySelector('.sm\\:grid-cols-3');
    expect(systemSection).not.toBeNull();
    const systemCards = systemSection?.querySelectorAll('.flex.items-center.gap-4');
    expect(systemCards?.length).toBe(3);
  });

  it('下段コンテンツスケルトンが2列表示される', () => {
    const { container } = render(<DashboardLoading />);
    const bottomGrid = container.querySelector('.xl\\:grid-cols-2');
    expect(bottomGrid).not.toBeNull();
    // 各列にスケルトンカードがある
    const bottomCards = bottomGrid?.querySelectorAll('.bg-gray-900.border.rounded-xl');
    expect(bottomCards?.length).toBe(2);
  });

  it('アクセシビリティ: ローディング中も DOM 構造が安定している', () => {
    const { container } = render(<DashboardLoading />);
    // スケルトン要素がある（空ではない）
    expect(container.innerHTML.length).toBeGreaterThan(100);
    // インタラクティブ要素が存在しない（ローディング中は操作不可）
    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBe(0);
    const links = container.querySelectorAll('a');
    expect(links.length).toBe(0);
  });
});
