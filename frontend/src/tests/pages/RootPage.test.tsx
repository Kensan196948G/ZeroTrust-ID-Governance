/**
 * RootPage テスト（Phase 22）
 *
 * src/app/page.tsx のカバレッジを 0% → 100% に向上させる。
 * vi.mock は hoisting されるため vi.hoisted() で事前に参照を確保する。
 *
 * 準拠: ISO27001:2022 A.8.2 テスト制御
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

// vi.mock は hoisting されるため vi.hoisted() で変数を事前確保
const { mockRedirect } = vi.hoisted(() => ({
  mockRedirect: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  redirect: mockRedirect,
}));

import RootPage from '@/app/page';

describe('RootPage', () => {
  it('redirect("/dashboard") が呼ばれる', () => {
    mockRedirect.mockClear();
    render(<RootPage />);
    expect(mockRedirect).toHaveBeenCalledWith('/dashboard');
  });

  it('redirect は1回だけ呼ばれる', () => {
    mockRedirect.mockClear();
    render(<RootPage />);
    expect(mockRedirect).toHaveBeenCalledTimes(1);
  });
});
