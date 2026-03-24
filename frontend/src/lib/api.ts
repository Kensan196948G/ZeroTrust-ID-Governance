/**
 * バックエンド API クライアント
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type User = {
  id: string;
  employee_id: string;
  username: string;
  email: string;
  display_name: string;
  user_type: 'employee' | 'contractor' | 'service_account' | 'admin';
  department: string | null;
  job_title: string | null;
  is_active: boolean;
  mfa_enabled: boolean;
  risk_score: number;
  entra_object_id: string | null;
  ad_dn: string | null;
  hengeone_id: string | null;
  last_login_at: string | null;
  created_at: string;
};

export type AccessRequest = {
  id: string;
  request_type: string;
  justification: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  created_at: string;
  expires_at: string | null;
};

export type AuditLog = {
  id: number;
  action: string;
  actor_id: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  actor_ip: string | null;
  created_at: string;
};

export type ApiResponse<T> = {
  success: boolean;
  data: T;
  errors: { message: string }[];
};

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const json: ApiResponse<T> = await response.json();
  if (!json.success) {
    throw new Error(json.errors[0]?.message ?? 'API request failed');
  }
  return json.data;
}

// ユーザ API
export const usersApi = {
  list: () => apiFetch<User[]>('/users'),
  get: (id: string) => apiFetch<User>(`/users/${id}`),
  create: (data: Partial<User>) =>
    apiFetch<User>('/users', { method: 'POST', body: JSON.stringify(data) }),
  disable: (id: string) =>
    apiFetch<User>(`/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: false }),
    }),
};

// アクセス申請 API
export const accessApi = {
  list: () => apiFetch<AccessRequest[]>('/access-requests'),
  pending: () => apiFetch<AccessRequest[]>('/access-requests/pending'),
  approve: (id: string, approverId: string) =>
    apiFetch<AccessRequest>(`/access-requests/${id}?action=approve&approver_id=${approverId}`, {
      method: 'PATCH',
    }),
  reject: (id: string, approverId: string) =>
    apiFetch<AccessRequest>(`/access-requests/${id}?action=reject&approver_id=${approverId}`, {
      method: 'PATCH',
    }),
};

// 監査ログ API
export const auditApi = {
  list: (params?: { limit?: number; offset?: number; action?: string }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params ?? {}).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
      )
    ).toString();
    return apiFetch<AuditLog[]>(`/audit-logs${qs ? '?' + qs : ''}`);
  },
};

// ワークフロー API
export const workflowsApi = {
  startReview: () =>
    apiFetch<{ task_id: string; status: string }>('/workflows/account-review', {
      method: 'POST',
    }),
  triggerProvisioning: (userId: string) =>
    apiFetch<{ task_id: string }>(`/workflows/provision/${userId}`, {
      method: 'POST',
    }),
};
