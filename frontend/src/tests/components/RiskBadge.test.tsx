import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiskBadge } from '@/components/RiskBadge';

describe('RiskBadge', () => {
  describe('低リスク（score < 30）', () => {
    it('スコア 0 で低リスク表示', () => {
      render(<RiskBadge score={0} />);
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText('低リスク')).toBeInTheDocument();
    });

    it('スコア 29 で低リスク表示', () => {
      render(<RiskBadge score={29} />);
      expect(screen.getByText('低リスク')).toBeInTheDocument();
    });

    it('低リスク時に green クラスを持つ', () => {
      const { container } = render(<RiskBadge score={10} />);
      const badge = container.firstChild as HTMLElement;
      expect(badge.className).toContain('green');
    });
  });

  describe('中リスク（30 ≤ score < 70）', () => {
    it('スコア 30 で中リスク表示', () => {
      render(<RiskBadge score={30} />);
      expect(screen.getByText('中リスク')).toBeInTheDocument();
    });

    it('スコア 69 で中リスク表示', () => {
      render(<RiskBadge score={69} />);
      expect(screen.getByText('中リスク')).toBeInTheDocument();
    });

    it('中リスク時に yellow クラスを持つ', () => {
      const { container } = render(<RiskBadge score={50} />);
      const badge = container.firstChild as HTMLElement;
      expect(badge.className).toContain('yellow');
    });
  });

  describe('高リスク（score ≥ 70）', () => {
    it('スコア 70 で高リスク表示', () => {
      render(<RiskBadge score={70} />);
      expect(screen.getByText('高リスク')).toBeInTheDocument();
    });

    it('スコア 100 で高リスク表示', () => {
      render(<RiskBadge score={100} />);
      expect(screen.getByText('高リスク')).toBeInTheDocument();
    });

    it('高リスク時に red クラスを持つ', () => {
      const { container } = render(<RiskBadge score={85} />);
      const badge = container.firstChild as HTMLElement;
      expect(badge.className).toContain('red');
    });
  });

  describe('showLabel プロパティ', () => {
    it('showLabel=false でラベルを非表示', () => {
      render(<RiskBadge score={80} showLabel={false} />);
      expect(screen.queryByText('高リスク')).not.toBeInTheDocument();
      expect(screen.getByText('80')).toBeInTheDocument();
    });

    it('showLabel=true（デフォルト）でラベルを表示', () => {
      render(<RiskBadge score={80} />);
      expect(screen.getByText('高リスク')).toBeInTheDocument();
    });
  });
});
