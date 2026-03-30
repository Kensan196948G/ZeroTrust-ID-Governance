/**
 * lib/api.ts ユニットテスト（Phase 20）
 *
 * 対象: tokenStore / apiFetch / authApi / usersApi / accessApi / auditApi / workflowsApi
 * カバレッジ目標: 19.81% → 80%+
 * 準拠: ISO27001 A.8.2 テスト制御 / NIST CSF DE.CM-01
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  tokenStore,
  authApi,
  usersApi,
  accessApi,
  auditApi,
  workflowsApi,
  type TokenPair,
  type User,
  type AccessRequest,
  type AuditLog,
  type ApiResponse,
} from '@/lib/api';

// ============================================================
// ヘルパー: fetch モックレスポンス生成
// ============================================================

function makeJsonResponse<T>(data: ApiResponse<T>, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeRawJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeErrorResponse(status: number, body?: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const mockFetch = vi.fn();

// ============================================================
// セットアップ
// ============================================================

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch);
  sessionStorage.clear();
  mockFetch.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

// ============================================================
// tokenStore テスト
// ============================================================

describe('tokenStore', () => {
  const samplePair: TokenPair = {
    access_token: 'access-abc',
    refresh_token: 'refresh-xyz',
    token_type: 'bearer',
  };

  it('初期状態は null を返す', () => {
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
  });

  it('setTokens でアクセストークンとリフレッシュトークンを保存する', () => {
    tokenStore.setTokens(samplePair);
    expect(tokenStore.getAccessToken()).toBe('access-abc');
    expect(tokenStore.getRefreshToken()).toBe('refresh-xyz');
  });

  it('clearTokens でトークンを削除する', () => {
    tokenStore.setTokens(samplePair);
    tokenStore.clearTokens();
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
  });

  it('isAuthenticated: トークンなしで false を返す', () => {
    expect(tokenStore.isAuthenticated()).toBe(false);
  });

  it('isAuthenticated: トークンあり で true を返す', () => {
    tokenStore.setTokens(samplePair);
    expect(tokenStore.isAuthenticated()).toBe(true);
  });

  it('clearTokens 後は isAuthenticated が false になる', () => {
    tokenStore.setTokens(samplePair);
    tokenStore.clearTokens();
    expect(tokenStore.isAuthenticated()).toBe(false);
  });
});

// ============================================================
// authApi テスト
// ============================================================

describe('authApi.login', () => {
  it('ログイン成功時にトークンを sessionStorage に保存する', async () => {
    const pair: TokenPair = {
      access_token: 'new-access',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
    };
    mockFetch.mockResolvedValueOnce(makeRawJsonResponse(pair));

    const result = await authApi.login('user-001', ['GlobalAdmin']);

    expect(result).toEqual(pair);
    expect(tokenStore.getAccessToken()).toBe('new-access');
    expect(tokenStore.getRefreshToken()).toBe('new-refresh');
  });

  it('ログイン失敗時（非 200）はエラーをスローする', async () => {
    mockFetch.mockResolvedValueOnce(makeErrorResponse(401));

    await expect(authApi.login('user-001', ['GlobalAdmin'])).rejects.toThrow(
      'ログインに失敗しました'
    );
  });
});

describe('authApi.logout', () => {
  it('ログアウト後はトークンが消去される', async () => {
    tokenStore.setTokens({
      access_token: 'tok',
      refresh_token: 'ref',
      token_type: 'bearer',
    });
    // logout は apiFetchNoContent を内部で使用 → 204 を返す
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await authApi.logout();

    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
  });

  it('logout API が失敗してもエラー応答でスローされる', async () => {
    mockFetch.mockResolvedValueOnce(
      makeRawJsonResponse({ detail: 'Unauthorized' }, 401)
    );

    await expect(authApi.logout()).rejects.toThrow();
  });
});

describe('authApi.refresh', () => {
  it('リフレッシュトークンがない場合はエラーをスローする', async () => {
    await expect(authApi.refresh()).rejects.toThrow(
      'リフレッシュトークンが存在しません'
    );
  });

  it('リフレッシュ成功時に新しいトークンを保存する', async () => {
    tokenStore.setTokens({
      access_token: 'old-access',
      refresh_token: 'old-refresh',
      token_type: 'bearer',
    });
    const newPair: TokenPair = {
      access_token: 'refreshed-access',
      refresh_token: 'refreshed-refresh',
      token_type: 'bearer',
    };
    mockFetch.mockResolvedValueOnce(makeRawJsonResponse(newPair));

    const result = await authApi.refresh();

    expect(result).toEqual(newPair);
    expect(tokenStore.getAccessToken()).toBe('refreshed-access');
  });

  it('リフレッシュ失敗時はトークンを消去してエラーをスローする', async () => {
    tokenStore.setTokens({
      access_token: 'old-access',
      refresh_token: 'old-refresh',
      token_type: 'bearer',
    });
    mockFetch.mockResolvedValueOnce(makeErrorResponse(401));

    await expect(authApi.refresh()).rejects.toThrow(
      'トークンのリフレッシュに失敗しました'
    );
    expect(tokenStore.getAccessToken()).toBeNull();
  });
});

// ============================================================
// apiFetch 経由のテスト（usersApi で代用）
// ============================================================

describe('usersApi.list', () => {
  const sampleUsers: User[] = [
    {
      id: 'u-001',
      employee_id: 'EMP001',
      username: 'alice',
      display_name: 'Alice',
      email: 'alice@example.com',
      user_type: 'employee',
      account_status: 'active',
      mfa_enabled: true,
      risk_score: 10,
      hire_date: '2020-01-01',
      created_at: '2020-01-01T00:00:00Z',
    },
  ];

  it('ユーザー一覧を取得する（パラメータなし）', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User[]>({ success: true, data: sampleUsers, errors: [] })
    );

    const result = await usersApi.list();

    expect(result).toEqual(sampleUsers);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/users'),
      expect.objectContaining({ headers: expect.any(Object) })
    );
  });

  it('クエリパラメータ付きで呼び出す', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User[]>({ success: true, data: sampleUsers, errors: [] })
    );

    await usersApi.list({ page: 2, per_page: 10, user_type: 'employee' });

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=10');
    expect(url).toContain('user_type=employee');
  });

  it('Authorization ヘッダーを自動付与する', async () => {
    tokenStore.setTokens({
      access_token: 'my-token',
      refresh_token: 'ref',
      token_type: 'bearer',
    });
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User[]>({ success: true, data: sampleUsers, errors: [] })
    );

    await usersApi.list();

    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Authorization']).toBe('Bearer my-token');
  });

  it('success: false の場合はエラーをスローする', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User[]>({
        success: false,
        data: [],
        errors: [{ message: 'forbidden' }],
      })
    );

    await expect(usersApi.list()).rejects.toThrow('forbidden');
  });

  it('エラーメッセージがない場合はデフォルトメッセージを使用する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User[]>({
        success: false,
        data: [],
        errors: [],
      })
    );

    await expect(usersApi.list()).rejects.toThrow('API request failed');
  });

  it('HTTP エラー（500）の場合は detail をスローする', async () => {
    mockFetch.mockResolvedValueOnce(
      makeRawJsonResponse({ detail: 'Internal server error' }, 500)
    );

    await expect(usersApi.list()).rejects.toThrow('Internal server error');
  });

  it('HTTP エラーで detail なしの場合はステータスをスローする', async () => {
    mockFetch.mockResolvedValueOnce(new Response('', { status: 503, statusText: 'Service Unavailable' }));

    await expect(usersApi.list()).rejects.toThrow('503');
  });
});

describe('usersApi.get', () => {
  it('特定ユーザーを取得する', async () => {
    const user: User = {
      id: 'u-001',
      employee_id: 'EMP001',
      username: 'alice',
      display_name: 'Alice',
      email: 'alice@example.com',
      user_type: 'employee',
      account_status: 'active',
      mfa_enabled: false,
      risk_score: 0,
      hire_date: '2020-01-01',
      created_at: '2020-01-01T00:00:00Z',
    };
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User>({ success: true, data: user, errors: [] })
    );

    const result = await usersApi.get('u-001');

    expect(result).toEqual(user);
    expect(mockFetch.mock.calls[0][0]).toContain('/users/u-001');
  });
});

describe('usersApi.create', () => {
  it('ユーザーを新規作成する', async () => {
    const newUser: User = {
      id: 'u-new',
      employee_id: 'EMP999',
      username: 'bob',
      display_name: 'Bob',
      email: 'bob@example.com',
      user_type: 'employee',
      account_status: 'active',
      mfa_enabled: false,
      risk_score: 0,
      hire_date: '2026-01-01',
      created_at: '2026-01-01T00:00:00Z',
    };
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User>({ success: true, data: newUser, errors: [] })
    );

    const result = await usersApi.create({
      employee_id: 'EMP999',
      username: 'bob',
      display_name: 'Bob',
      email: 'bob@example.com',
      user_type: 'employee',
      hire_date: '2026-01-01',
    });

    expect(result).toEqual(newUser);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/users');
    expect(options.method).toBe('POST');
  });
});

describe('usersApi.update', () => {
  it('ユーザー情報を更新する', async () => {
    const updated: User = {
      id: 'u-001',
      employee_id: 'EMP001',
      username: 'alice',
      display_name: 'Alice Updated',
      email: 'alice@example.com',
      user_type: 'employee',
      account_status: 'active',
      mfa_enabled: true,
      risk_score: 5,
      hire_date: '2020-01-01',
      created_at: '2020-01-01T00:00:00Z',
    };
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<User>({ success: true, data: updated, errors: [] })
    );

    const result = await usersApi.update('u-001', { display_name: 'Alice Updated' });

    expect(result.display_name).toBe('Alice Updated');
    expect(mockFetch.mock.calls[0][1].method).toBe('PATCH');
  });
});

describe('usersApi.disable', () => {
  it('ユーザーを無効化する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<{ message: string }>({
        success: true,
        data: { message: 'deleted' },
        errors: [],
      })
    );

    const result = await usersApi.disable('u-001');

    expect(result.message).toBe('deleted');
    expect(mockFetch.mock.calls[0][1].method).toBe('DELETE');
  });
});

// ============================================================
// 401 リフレッシュリトライフロー
// ============================================================

describe('apiFetch: 401 リフレッシュリトライ', () => {
  it('401 → リフレッシュ成功 → 元リクエスト再実行', async () => {
    tokenStore.setTokens({
      access_token: 'expired-token',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
    });

    const users: User[] = [];
    const newPair: TokenPair = {
      access_token: 'new-token',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
    };

    // 1回目: 401（アクセストークン期限切れ）
    mockFetch
      .mockResolvedValueOnce(makeErrorResponse(401))
      // 2回目: リフレッシュ成功
      .mockResolvedValueOnce(makeRawJsonResponse(newPair))
      // 3回目: 元リクエスト再実行 → 成功
      .mockResolvedValueOnce(
        makeJsonResponse<User[]>({ success: true, data: users, errors: [] })
      );

    const result = await usersApi.list();

    expect(result).toEqual(users);
    expect(mockFetch).toHaveBeenCalledTimes(3);
    // 3回目のリクエストは新しいトークンを使用
    const retryHeaders = mockFetch.mock.calls[2][1].headers;
    expect(retryHeaders['Authorization']).toBe('Bearer new-token');
  });

  it('401 → リフレッシュ失敗 → トークン消去してエラーをスロー', async () => {
    tokenStore.setTokens({
      access_token: 'expired-token',
      refresh_token: 'bad-refresh',
      token_type: 'bearer',
    });

    // 1回目: 401
    mockFetch
      .mockResolvedValueOnce(makeErrorResponse(401))
      // 2回目: リフレッシュも失敗
      .mockResolvedValueOnce(makeErrorResponse(401));

    await expect(usersApi.list()).rejects.toThrow(
      'セッションが期限切れです。再ログインしてください。'
    );
    expect(tokenStore.getAccessToken()).toBeNull();
  });

  it('401 → リフレッシュ成功 → 再実行が失敗してもエラーは起きない', async () => {
    tokenStore.setTokens({
      access_token: 'expired',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
    });
    const newPair: TokenPair = {
      access_token: 'new-token',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
    };

    // 1回目: 401 → 2回目: refresh成功 → 3回目: 再実行が 403
    mockFetch
      .mockResolvedValueOnce(makeErrorResponse(401))
      .mockResolvedValueOnce(makeRawJsonResponse(newPair))
      .mockResolvedValueOnce(makeErrorResponse(403));

    // 再実行が ok でない場合はトークン消去してエラー
    await expect(usersApi.list()).rejects.toThrow(
      'セッションが期限切れです。再ログインしてください。'
    );
  });

  it('401 → リフレッシュ成功 → 再実行は ok だが success:false の場合はエラーをスロー', async () => {
    tokenStore.setTokens({
      access_token: 'expired',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
    });
    const newPair: TokenPair = {
      access_token: 'new-token',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
    };

    mockFetch
      .mockResolvedValueOnce(makeErrorResponse(401))
      .mockResolvedValueOnce(makeRawJsonResponse(newPair))
      // 3回目: 200 ok だが success:false
      .mockResolvedValueOnce(
        makeJsonResponse<User[]>({
          success: false,
          data: [],
          errors: [{ message: 'retry failed' }],
        })
      );

    await expect(usersApi.list()).rejects.toThrow('retry failed');
  });

  it('_tryRefreshToken: fetch が例外を投げた場合は false を返す', async () => {
    tokenStore.setTokens({
      access_token: 'expired',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
    });

    mockFetch
      .mockResolvedValueOnce(makeErrorResponse(401))
      // リフレッシュ時に fetch 自体が例外
      .mockRejectedValueOnce(new Error('Network error'));

    await expect(usersApi.list()).rejects.toThrow(
      'セッションが期限切れです。再ログインしてください。'
    );
  });

  it('リフレッシュトークンなしの場合は即座にトークン消去してエラーをスロー', async () => {
    tokenStore.setTokens({
      access_token: 'expired',
      refresh_token: 'placeholder',
      token_type: 'bearer',
    });
    // refresh_token だけ手動で削除
    sessionStorage.removeItem('ztid_refresh_token');

    mockFetch.mockResolvedValueOnce(makeErrorResponse(401));

    await expect(usersApi.list()).rejects.toThrow(
      'セッションが期限切れです。再ログインしてください。'
    );
  });
});

// ============================================================
// accessApi テスト
// ============================================================

describe('accessApi', () => {
  const sampleRequest: AccessRequest = {
    id: 'req-001',
    request_type: 'provision',
    justification: 'Need access for project X',
    status: 'pending',
    created_at: '2026-01-01T00:00:00Z',
    expires_at: null,
  };

  it('list: アクセス申請一覧を取得する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AccessRequest[]>({
        success: true,
        data: [sampleRequest],
        errors: [],
      })
    );

    const result = await accessApi.list();

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('req-001');
  });

  it('pending: 保留中の申請一覧を取得する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AccessRequest[]>({
        success: true,
        data: [sampleRequest],
        errors: [],
      })
    );

    const result = await accessApi.pending();

    expect(mockFetch.mock.calls[0][0]).toContain('/access-requests/pending');
    expect(result[0].status).toBe('pending');
  });

  it('create: 新規申請を作成する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AccessRequest>({
        success: true,
        data: sampleRequest,
        errors: [],
      })
    );

    const result = await accessApi.create({ justification: 'Need access for project X' });

    expect(result.id).toBe('req-001');
    expect(mockFetch.mock.calls[0][1].method).toBe('POST');
  });

  it('approve: 申請を承認する', async () => {
    const approved: AccessRequest = { ...sampleRequest, status: 'approved' };
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AccessRequest>({ success: true, data: approved, errors: [] })
    );

    const result = await accessApi.approve('req-001');

    expect(result.status).toBe('approved');
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('action=approve');
    expect(mockFetch.mock.calls[0][1].method).toBe('PATCH');
  });

  it('reject: 申請を却下する', async () => {
    const rejected: AccessRequest = { ...sampleRequest, status: 'rejected' };
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AccessRequest>({ success: true, data: rejected, errors: [] })
    );

    const result = await accessApi.reject('req-001');

    expect(result.status).toBe('rejected');
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('action=reject');
  });
});

// ============================================================
// auditApi テスト
// ============================================================

describe('auditApi', () => {
  const sampleLog: AuditLog = {
    id: 1,
    event_id: 'evt-001',
    event_time: '2026-01-01T00:00:00Z',
    event_type: 'login',
    source_system: 'portal',
    actor_user_id: 'u-001',
    action: 'user_login',
    result: 'success',
    risk_score: 5,
  };

  it('list: 監査ログ一覧を取得する（パラメータなし）', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AuditLog[]>({ success: true, data: [sampleLog], errors: [] })
    );

    const result = await auditApi.list();

    expect(result).toHaveLength(1);
    expect(mockFetch.mock.calls[0][0]).toContain('/audit-logs');
  });

  it('list: クエリパラメータ付きで取得する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse<AuditLog[]>({ success: true, data: [sampleLog], errors: [] })
    );

    await auditApi.list({ page: 1, event_type: 'login', result: 'success' });

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('event_type=login');
    expect(url).toContain('result=success');
  });

  it('exportCsv: Blob を返す', async () => {
    const csvContent = 'event_id,event_type\nevt-001,login';
    mockFetch.mockResolvedValueOnce(
      new Response(csvContent, {
        status: 200,
        headers: { 'Content-Type': 'text/csv' },
      })
    );

    const blob = await auditApi.exportCsv();

    // jsdom 環境では Response.blob() が Node.js の Blob を返すため instanceof ではなく型チェック
    expect(typeof blob.size).toBe('number');
    expect(typeof blob.text).toBe('function');
    expect(mockFetch.mock.calls[0][0]).toContain('/audit-logs/export');
  });

  it('exportCsv: アクセストークンがある場合は Authorization ヘッダーを付与する', async () => {
    tokenStore.setTokens({
      access_token: 'my-access-token',
      refresh_token: 'ref',
      token_type: 'bearer',
    });
    mockFetch.mockResolvedValueOnce(
      new Response('csv-data', { status: 200 })
    );

    await auditApi.exportCsv({ from_time: '2026-01-01', to_time: '2026-12-31' });

    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Authorization']).toBe('Bearer my-access-token');
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('from_time=2026-01-01');
  });

  it('exportCsv: エラー時はエラーをスローする', async () => {
    mockFetch.mockResolvedValueOnce(makeErrorResponse(500));

    await expect(auditApi.exportCsv()).rejects.toThrow('CSV export failed: 500');
  });

  it('exportCsv: アクセストークンなしは Authorization ヘッダーを付与しない', async () => {
    mockFetch.mockResolvedValueOnce(new Response('csv', { status: 200 }));

    await auditApi.exportCsv();

    const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>;
    expect(headers['Authorization']).toBeUndefined();
  });
});

// ============================================================
// workflowsApi テスト
// ============================================================

describe('workflowsApi', () => {
  const taskResponse = { task_id: 'task-001', status: 'started' };

  const workflows = [
    { name: 'accountReview', fn: () => workflowsApi.accountReview(), path: '/workflows/account-review' },
    { name: 'consistencyCheck', fn: () => workflowsApi.consistencyCheck(), path: '/workflows/consistency-check' },
    { name: 'riskScan', fn: () => workflowsApi.riskScan(), path: '/workflows/risk-scan' },
    { name: 'pimExpiry', fn: () => workflowsApi.pimExpiry(), path: '/workflows/pim-expiry' },
    { name: 'mfaEnforcement', fn: () => workflowsApi.mfaEnforcement(), path: '/workflows/mfa-enforcement' },
  ] as const;

  for (const { name, fn, path } of workflows) {
    it(`${name}: POST リクエストを送信しタスク情報を返す`, async () => {
      mockFetch.mockResolvedValueOnce(
        makeJsonResponse({ success: true, data: taskResponse, errors: [] })
      );

      const result = await fn();

      expect(result).toEqual(taskResponse);
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain(path);
      expect(mockFetch.mock.calls[0][1].method).toBe('POST');
    });
  }

  it('quarterlyReview: POST リクエストを送信しタスク情報を返す', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse({ success: true, data: taskResponse, errors: [] })
    );

    const result = await workflowsApi.quarterlyReview();

    expect(result).toEqual(taskResponse);
    expect(mockFetch.mock.calls[0][0]).toContain('/workflows/quarterly-review');
  });

  it('provision: ユーザーIDを含む URL で POST する', async () => {
    mockFetch.mockResolvedValueOnce(
      makeJsonResponse({ success: true, data: { task_id: 'prov-001' }, errors: [] })
    );

    const result = await workflowsApi.provision('u-001');

    expect(result.task_id).toBe('prov-001');
    expect(mockFetch.mock.calls[0][0]).toContain('/workflows/provision/u-001');
  });
});

// ============================================================
// apiFetchNoContent テスト（authApi.logout 経由）
// ============================================================

describe('apiFetchNoContent', () => {
  it('204 応答は正常完了する', async () => {
    tokenStore.setTokens({
      access_token: 'tok',
      refresh_token: 'ref',
      token_type: 'bearer',
    });
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(authApi.logout()).resolves.toBeUndefined();
  });

  it('200 応答も正常完了する', async () => {
    tokenStore.setTokens({
      access_token: 'tok',
      refresh_token: 'ref',
      token_type: 'bearer',
    });
    // logout は apiFetchNoContent を呼ぶため 200 は ok として正常終了
    mockFetch.mockResolvedValueOnce(new Response('{}', { status: 200 }));

    await expect(authApi.logout()).resolves.toBeUndefined();
  });

  it('エラーレスポンスで detail がある場合はそれをスローする', async () => {
    mockFetch.mockResolvedValueOnce(
      makeRawJsonResponse({ detail: 'Not found' }, 404)
    );

    await expect(authApi.logout()).rejects.toThrow('Not found');
  });

  it('エラーレスポンスで JSON パース失敗の場合はステータスをスローする', async () => {
    mockFetch.mockResolvedValueOnce(
      new Response('not-json', { status: 500, statusText: 'Server Error' })
    );

    await expect(authApi.logout()).rejects.toThrow('500');
  });
});
