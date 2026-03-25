import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Shield } from 'lucide-react';
import { StatCard } from '@/components/StatCard';

describe('StatCard', () => {
  describe('基本レンダリング', () => {
    it('タイトルと値を表示する', () => {
      render(<StatCard title="高リスクユーザー" value={42} icon={Shield} />);
      expect(screen.getByText('高リスクユーザー')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('文字列の値を表示する', () => {
      render(<StatCard title="ステータス" value="正常" icon={Shield} />);
      expect(screen.getByText('正常')).toBeInTheDocument();
    });

    it('trend なしではトレンド情報を表示しない', () => {
      render(<StatCard title="合計" value={100} icon={Shield} />);
      expect(screen.queryByText(/▲|▼/)).not.toBeInTheDocument();
    });
  });

  describe('trend プロパティ', () => {
    it('正の trend 値で ▲ と赤クラスを表示する', () => {
      render(
        <StatCard title="リスク数" value={10} icon={Shield} trend={{ value: 5, label: '前週比' }} />
      );
      const trendEl = screen.getByText(/▲/);
      expect(trendEl).toBeInTheDocument();
      expect(trendEl.textContent).toContain('5%');
      expect(trendEl.textContent).toContain('前週比');
      expect(trendEl.className).toContain('red');
    });

    it('負の trend 値で ▼ と緑クラスを表示する', () => {
      render(
        <StatCard title="リスク数" value={8} icon={Shield} trend={{ value: -3, label: '前週比' }} />
      );
      const trendEl = screen.getByText(/▼/);
      expect(trendEl).toBeInTheDocument();
      expect(trendEl.textContent).toContain('3%');
      expect(trendEl.className).toContain('green');
    });

    it('trend 値 0 で ▼ と緑クラスを表示する（境界値）', () => {
      render(
        <StatCard title="リスク数" value={5} icon={Shield} trend={{ value: 0, label: '変化なし' }} />
      );
      const trendEl = screen.getByText(/▼/);
      expect(trendEl).toBeInTheDocument();
      expect(trendEl.className).toContain('green');
    });

    it('絶対値でパーセントを表示する（負数でも正表示）', () => {
      render(
        <StatCard title="リスク数" value={5} icon={Shield} trend={{ value: -10, label: 'テスト' }} />
      );
      expect(screen.getByText(/10%/)).toBeInTheDocument();
      expect(screen.queryByText(/-10%/)).not.toBeInTheDocument();
    });
  });

  describe('variant プロパティ', () => {
    it('variant=danger で red クラスを持つ', () => {
      const { container } = render(
        <StatCard title="危険" value={99} icon={Shield} variant="danger" />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('red');
    });

    it('variant=warning で yellow クラスを持つ', () => {
      const { container } = render(
        <StatCard title="警告" value={50} icon={Shield} variant="warning" />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('yellow');
    });

    it('variant=success で green クラスを持つ', () => {
      const { container } = render(
        <StatCard title="正常" value={10} icon={Shield} variant="success" />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('green');
    });

    it('variant 未指定（default）でも正常にレンダリングされる', () => {
      const { container } = render(<StatCard title="デフォルト" value={0} icon={Shield} />);
      expect(container.firstChild).toBeInTheDocument();
    });
  });
});
