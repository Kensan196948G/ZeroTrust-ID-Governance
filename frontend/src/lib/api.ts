/**
 * バックエンド API クライアント
 *
 * JWT 認証対応: Authorization: Bearer ヘッダーを自動付与
 * トークン管理: sessionStorage ベース（タブクローズで失効）
 *
 * 準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-01
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================
// 型定義（バックエンド Pydantic スキーマに準拠）
// ============================================================

/** バックエンド UserResponse スキーマ準拠 */
export type User = {
  id: string;
  employee_id: string;
  username: string;
  display_name: string;
  email: string;
  user_type: 'employee' | 'contractor' | 'partner' | 'admin';
  account_status: 'active' | 'disabled' | 'suspended';
  mfa_enabled: boolean;
  risk_score: number;
  hire_date: string;   // ISO 8601 日付文字列 (YYYY-MM-DD)
  created_at: string;  // ISO 8601 日時文字列
};

/** バックエンド AccessRequestResponse スキーマ準拠 */
export type AccessRequest = {
  id: string;
  request_type: string;
  justification: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  created_at: string;
  expires_at: string | null;
};

/** バックエンド AuditLog モデル準拠 */
export type AuditLog = {
  id: number;
  event_id: string;
  event_time: string;
  event_type: string;
  source_system: string;
  actor_user_id: string | null;
  action: string;
  result: string;
  risk_score: number | null;
};

/** 統一 API レスポンス形式 */
export type ApiResponse<T> = {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
  errors: { message: string }[];
};

/** JWT トークンペア */
export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

// ============================================================
// トークン管理（sessionStorage: タブクローズで自動失効）
// ============================================================

const TOKEN_KEY = 'ztid_access_token';
const REFRESH_KEY = 'ztid_refresh_token';

export const tokenStore = {
  getAccessToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem(TOKEN_KEY);
  },
  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem(REFRESH_KEY);
  },
  setTokens: (pair: TokenPair): void => {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem(TOKEN_KEY, pair.access_token);
    sessionStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clearTokens: (): void => {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  },
  isAuthenticated: (): boolean => {
    return tokenStore.getAccessToken() !== null;
  },
};

// ============================================================
// コア Fetch ユーティリティ（認証ヘッダー自動付与）
// ============================================================

/** 401 時にリフレッシュを試みるフラグ（無限ループ防止） */
let _isRefreshing = false;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const accessToken = tokenStore.getAccessToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers,
  });

  // 401 Unauthorized: トークンリフレッシュを試みる
  if (response.status === 401 && !_isRefreshing) {
    const refreshed = await _tryRefreshToken();
    if (refreshed) {
      // リフレッシュ成功: 元のリクエストを再実行
      const newToken = tokenStore.getAccessToken();
      const retryResponse = await fetch(`${API_BASE}/api/v1${path}`, {
        ...options,
        headers: {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        },
      });
      if (retryResponse.ok) {
        const json: ApiResponse<T> = await retryResponse.json();
        if (!json.success) {
          throw new Error(json.errors[0]?.message ?? 'API request failed');
        }
        return json.data;
      }
    }
    // リフレッシュ失敗: セッション失効
    tokenStore.clearTokens();
    throw new Error('セッションが期限切れです。再ログインしてください。');
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const detail = (errorBody as { detail?: string }).detail;
    throw new Error(detail ?? `API error: ${response.status} ${response.statusText}`);
  }

  const json: ApiResponse<T> = await response.json();
  if (!json.success) {
    throw new Error(json.errors[0]?.message ?? 'API request failed');
  }
  return json.data;
}

/** 204 No Content レスポンス向け（レスポンスボディなし） */
async function apiFetchNoContent(path: string, options?: RequestInit): Promise<void> {
  const accessToken = tokenStore.getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE}/api/v1${path}`, { ...options, headers });

  if (!response.ok && response.status !== 204) {
    const errorBody = await response.json().catch(() => ({}));
    const detail = (errorBody as { detail?: string }).detail;
    throw new Error(detail ?? `API error: ${response.status}`);
  }
}

async function _tryRefreshToken(): Promise<boolean> {
  _isRefreshing = true;
  try {
    const refreshToken = tokenStore.getRefreshToken();
    if (!refreshToken) return false;

    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return false;

    const pair: TokenPair = await response.json();
    tokenStore.setTokens(pair);
    return true;
  } catch {
    return false;
  } finally {
    _isRefreshing = false;
  }
}

// ============================================================
// 認証 API
// ============================================================

export const authApi = {
  /** ログイン（開発用: ユーザーID直接指定でトークン取得） */
  login: async (userId: string, roles: string[]): Promise<TokenPair> => {
    // 本番では /api/v1/auth/login (username/password) を使用する
    // 現段階では開発用エンドポイントとして token 直接生成を使用
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, roles }),
    });
    if (!response.ok) {
      throw new Error('ログインに失敗しました');
    }
    const pair: TokenPair = await response.json();
    tokenStore.setTokens(pair);
    return pair;
  },

  /** ログアウト（アクセストークンを Redis ブラックリストへ登録） */
  logout: async (): Promise<void> => {
    await apiFetchNoContent('/auth/logout', { method: 'POST' });
    tokenStore.clearTokens();
  },

  /** トークンリフレッシュ（手動呼び出し用） */
  refresh: async (): Promise<TokenPair> => {
    const refreshToken = tokenStore.getRefreshToken();
    if (!refreshToken) throw new Error('リフレッシュトークンが存在しません');

    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) {
      tokenStore.clearTokens();
      throw new Error('トークンのリフレッシュに失敗しました');
    }
    const pair: TokenPair = await response.json();
    tokenStore.setTokens(pair);
    return pair;
  },
};

// ============================================================
// ユーザー API
// ============================================================

export const usersApi = {
  list: (params?: { page?: number; per_page?: number; user_type?: string; account_status?: string }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : '';
    return apiFetch<User[]>(`/users${qs}`);
  },
  get: (id: string) => apiFetch<User>(`/users/${id}`),
  create: (data: {
    employee_id: string;
    username: string;
    display_name: string;
    email: string;
    user_type: string;
    hire_date: string;
    job_title?: string;
    department_id?: string;
  }) => apiFetch<User>('/users', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: { display_name?: string; job_title?: string; account_status?: string }) =>
    apiFetch<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  disable: (id: string) =>
    apiFetch<{ message: string }>(`/users/${id}`, { method: 'DELETE' }),
};

// ============================================================
// アクセス申請 API
// ============================================================

export const accessApi = {
  list: () => apiFetch<AccessRequest[]>('/access-requests'),
  pending: () => apiFetch<AccessRequest[]>('/access-requests/pending'),
  create: (data: { justification: string; request_type?: string; role_id?: string; resource_id?: string; expires_at?: string }) =>
    apiFetch<AccessRequest>('/access-requests', { method: 'POST', body: JSON.stringify(data) }),
  approve: (id: string) =>
    apiFetch<AccessRequest>(`/access-requests/${id}?action=approve`, { method: 'PATCH' }),
  reject: (id: string) =>
    apiFetch<AccessRequest>(`/access-requests/${id}?action=reject`, { method: 'PATCH' }),
};

// ============================================================
// 監査ログ API
// ============================================================

export const auditApi = {
  list: (params?: {
    page?: number;
    per_page?: number;
    event_type?: string;
    source_system?: string;
    result?: string;
    from_time?: string;
    to_time?: string;
  }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : '';
    return apiFetch<AuditLog[]>(`/audit-logs${qs}`);
  },
  exportCsv: async (params?: { from_time?: string; to_time?: string }): Promise<Blob> => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : '';
    const accessToken = tokenStore.getAccessToken();
    const response = await fetch(`${API_BASE}/api/v1/audit-logs/export${qs}`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
    if (!response.ok) throw new Error(`CSV export failed: ${response.status}`);
    return response.blob();
  },
};

// ============================================================
// ワークフロー API
// ============================================================

export const workflowsApi = {
  accountReview: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/account-review', { method: 'POST' }),
  quarterlyReview: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/quarterly-review', { method: 'POST' }),
  consistencyCheck: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/consistency-check', { method: 'POST' }),
  riskScan: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/risk-scan', { method: 'POST' }),
  pimExpiry: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/pim-expiry', { method: 'POST' }),
  mfaEnforcement: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/mfa-enforcement', { method: 'POST' }),
  provision: (userId: string) =>
    apiFetch<{ task_id: string }>(`/workflows/provision/${userId}`, { method: 'POST' }),
};
