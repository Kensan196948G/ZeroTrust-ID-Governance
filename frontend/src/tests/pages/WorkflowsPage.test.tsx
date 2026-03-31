import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// SWR mock
vi.mock('swr', () => ({
  default: vi.fn(),
}));
import useSWR from 'swr';
const mockUseSWR = vi.mocked(useSWR);

// API mock
vi.mock('@/lib/api', () => ({
  workflowsApi: {
    quarterlyReview: vi.fn(),
    consistencyCheck: vi.fn(),
    riskScan: vi.fn(),
    pimExpiry: vi.fn(),
    mfaEnforcement: vi.fn(),
  },
}));
import { workflowsApi } from '@/lib/api';

import WorkflowsPage from '@/app/(dashboard)/workflows/page';

describe('WorkflowsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function setupSWR(healthStatus: { status: string } | undefined) {
    mockUseSWR.mockReturnValue({
      data: healthStatus,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      isValidating: false,
    } as ReturnType<typeof useSWR>);
  }

  it('5つのワークフローカードが表示される', () => {
    setupSWR({ status: 'ok' });
    render(<WorkflowsPage />);

    const cards = screen.getAllByText('手動実行');
    expect(cards).toHaveLength(5);
  });

  it('各ワークフローの名前と説明が表示される', () => {
    setupSWR({ status: 'ok' });
    render(<WorkflowsPage />);

    expect(screen.getByText('四半期アクセス棚卸')).toBeInTheDocument();
    expect(screen.getByText('整合性チェック')).toBeInTheDocument();
    expect(screen.getByText('リスクスキャン')).toBeInTheDocument();
    expect(screen.getByText('PIM 期限切れ処理')).toBeInTheDocument();
    expect(screen.getByText('MFA 未設定アカウント対応')).toBeInTheDocument();

    // 説明文の一部を確認
    expect(screen.getByText(/全ユーザーの3システム整合性チェック/)).toBeInTheDocument();
    expect(screen.getByText(/3システム間のユーザー情報乖離を検出/)).toBeInTheDocument();
  });

  it('システムオンライン時に「システム稼働中」表示', () => {
    setupSWR({ status: 'ok' });
    render(<WorkflowsPage />);

    expect(screen.getByText('システム稼働中')).toBeInTheDocument();
  });

  it('システムオフライン時にボタンが disabled', () => {
    setupSWR({ status: 'error' });
    render(<WorkflowsPage />);

    expect(screen.getByText('確認中...')).toBeInTheDocument();

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    executeButtons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  it('手動実行ボタンクリックでワークフロー実行', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    vi.mocked(workflowsApi.quarterlyReview).mockResolvedValue({
      task_id: 'task-123',
      status: 'started',
    });

    render(<WorkflowsPage />);

    // 最初のワークフロー（四半期アクセス棚卸）の実行ボタンをクリック
    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    await user.click(executeButtons[0]);

    await waitFor(() => {
      expect(workflowsApi.quarterlyReview).toHaveBeenCalled();
    });
  });

  it('実行中は「実行中...」表示でボタン disabled', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    // 遅延する Promise を作成
    let resolvePromise: (value: { task_id: string; status: string }) => void;
    const pendingPromise = new Promise<{ task_id: string; status: string }>((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(workflowsApi.quarterlyReview).mockReturnValue(pendingPromise);

    render(<WorkflowsPage />);

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    await user.click(executeButtons[0]);

    // 実行中の表示を確認
    await waitFor(() => {
      expect(screen.getByText('実行中...')).toBeInTheDocument();
    });

    // Promise を解決
    await act(async () => {
      resolvePromise!({ task_id: 'task-123', status: 'completed' });
    });
  });

  it('成功時に結果メッセージ表示', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    vi.mocked(workflowsApi.quarterlyReview).mockResolvedValue({
      task_id: 'task-456',
      status: 'completed',
    });

    render(<WorkflowsPage />);

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    await user.click(executeButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/タスクID: task-456/)).toBeInTheDocument();
    });
  });

  it('失敗時にエラーメッセージ表示', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    vi.mocked(workflowsApi.quarterlyReview).mockRejectedValue(
      new Error('ネットワークエラー')
    );

    render(<WorkflowsPage />);

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    await user.click(executeButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('ネットワークエラー')).toBeInTheDocument();
    });
  });

  it('非 Error オブジェクト reject 時にフォールバックメッセージ表示（line 100）', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    // string を reject することで `err instanceof Error` の else ブランチをカバー
    vi.mocked(workflowsApi.quarterlyReview).mockRejectedValue('文字列エラー');

    render(<WorkflowsPage />);

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    await user.click(executeButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('エラーが発生しました')).toBeInTheDocument();
    });
  });

  it('実行中に再クリックしても二重実行されない（line 83 早期 return）', async () => {
    const user = userEvent.setup();
    setupSWR({ status: 'ok' });

    // 解決しない Promise で実行中状態を維持
    const neverResolve = new Promise<{ task_id: string; status: string }>(() => {});
    vi.mocked(workflowsApi.quarterlyReview).mockReturnValue(neverResolve);

    render(<WorkflowsPage />);

    const executeButtons = screen.getAllByText('手動実行').map((el) => el.closest('button')!);
    // 1回目クリック → 実行中状態になる
    await user.click(executeButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('実行中...')).toBeInTheDocument();
    });

    // 2回目クリック → 早期 return（line 83）で API は1回しか呼ばれない
    await user.click(executeButtons[0]);
    expect(workflowsApi.quarterlyReview).toHaveBeenCalledTimes(1);
  });
});
