-- ZeroTrust-ID-Governance 初期スキーマ
-- 設計仕様書 3.1 DB設計準拠

-- 拡張機能
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 部署テーブル
CREATE TABLE IF NOT EXISTS departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    parent_id   UUID REFERENCES departments(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ユーザテーブル
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     VARCHAR(20) UNIQUE NOT NULL,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    user_type       VARCHAR(20) NOT NULL DEFAULT 'employee'
                    CHECK (user_type IN ('employee','contractor','service_account','admin')),
    department      VARCHAR(100),
    job_title       VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT false,
    risk_score      SMALLINT NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
    -- 外部システム連携 ID
    entra_object_id VARCHAR(36) UNIQUE,
    ad_dn           TEXT UNIQUE,
    hengeone_id     VARCHAR(50) UNIQUE,
    -- メタデータ
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ロールテーブル
CREATE TABLE IF NOT EXISTS roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    role_type       VARCHAR(20) NOT NULL DEFAULT 'standard'
                    CHECK (role_type IN ('standard','privileged','pim')),
    max_duration    INTERVAL,  -- PIM ロールの最大有効期間
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ユーザ・ロール中間テーブル（RBAC）
CREATE TABLE IF NOT EXISTS user_roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id),
    expires_at  TIMESTAMPTZ,  -- NULL = 無期限
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, role_id)
);

-- リソーステーブル
CREATE TABLE IF NOT EXISTS resources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    resource_type   VARCHAR(30) NOT NULL
                    CHECK (resource_type IN ('application','fileserver','database','api','sharepoint')),
    description     TEXT,
    owner_id        UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- アクセス申請テーブル（GOV-003）
CREATE TABLE IF NOT EXISTS access_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id    UUID NOT NULL REFERENCES users(id),
    target_user_id  UUID REFERENCES users(id),
    role_id         UUID REFERENCES roles(id),
    resource_id     UUID REFERENCES resources(id),
    request_type    VARCHAR(10) NOT NULL DEFAULT 'grant'
                    CHECK (request_type IN ('grant','revoke','extend')),
    justification   TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected','expired')),
    approver_id     UUID REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 監査ログテーブル（AUD-001 / ISO27001 A.5.28 チェーンハッシュ）
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    action      VARCHAR(100) NOT NULL,
    actor_id    UUID,
    resource_id TEXT,
    details     JSONB NOT NULL DEFAULT '{}',
    actor_ip    INET,
    hash        VARCHAR(64) NOT NULL,  -- SHA256 チェーンハッシュ
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);
CREATE INDEX IF NOT EXISTS idx_users_entra_id ON users(entra_object_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_expires_at ON user_roles(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_access_requests_status ON access_requests(status);
CREATE INDEX IF NOT EXISTS idx_access_requests_requester ON access_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- 初期ロール
INSERT INTO roles (name, description, role_type) VALUES
    ('GlobalAdmin',         'グローバル管理者',         'privileged'),
    ('UserAdmin',           'ユーザ管理者',              'standard'),
    ('SecurityAdmin',       'セキュリティ管理者',        'privileged'),
    ('FinanceAuditor',      '財務監査員',                'standard'),
    ('Developer',           '開発者',                   'standard'),
    ('ProductionDeployer',  '本番デプロイ担当',          'privileged'),
    ('Requester',           '申請者',                   'standard'),
    ('Approver',            '承認者',                   'standard'),
    ('ReadOnly',            '参照専用',                  'standard')
ON CONFLICT (name) DO NOTHING;
