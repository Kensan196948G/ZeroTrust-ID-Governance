"""initial_schema

Revision ID: db955898f2c3
Revises:
Create Date: 2026-03-24 14:43:08.233391

全テーブルの初回作成マイグレーション
準拠: ISO27001 A.8.9 設定管理 / 設計仕様書 2.1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision: str = "db955898f2c3"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─────────────────────────────────────────
    # departments テーブル（自己参照による階層構造）
    # ─────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────
    # users テーブル
    # ─────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", sa.String(20), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("job_title", sa.String(200), nullable=True),
        sa.Column(
            "user_type",
            sa.String(20),
            sa.CheckConstraint("user_type IN ('employee','contractor','partner','admin')"),
            nullable=False,
        ),
        sa.Column("account_status", sa.String(20), nullable=False, server_default="active"),
        # 外部システム連携 ID
        sa.Column("entra_object_id", sa.String(36), nullable=True),
        sa.Column("ad_dn", sa.Text, nullable=True),
        sa.Column("hengeone_id", sa.String(100), nullable=True),
        # 在籍情報
        sa.Column("hire_date", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        # セキュリティ
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "risk_score",
            sa.Integer,
            sa.CheckConstraint("risk_score BETWEEN 0 AND 100"),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────
    # roles テーブル
    # ─────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "role_type",
            sa.String(20),
            sa.CheckConstraint("role_type IN ('business','technical','privileged')"),
            nullable=False,
        ),
        sa.Column("is_privileged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("max_duration", sa.Interval, nullable=True),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────
    # user_roles テーブル（ユーザ-ロール中間テーブル）
    # ─────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # ─────────────────────────────────────────
    # resources テーブル
    # ─────────────────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_name", sa.String(200), nullable=False),
        sa.Column(
            "resource_type",
            sa.String(50),
            sa.CheckConstraint("resource_type IN ('application','server','database','api','storage')"),
            nullable=False,
        ),
        sa.Column(
            "sensitivity",
            sa.String(20),
            sa.CheckConstraint("sensitivity IN ('public','internal','confidential','secret')"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────
    # access_requests テーブル
    # ─────────────────────────────────────────
    op.create_table(
        "access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id"), nullable=True),
        sa.Column(
            "request_type",
            sa.String(20),
            sa.CheckConstraint("request_type IN ('grant','revoke','extend')"),
            nullable=False,
        ),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────
    # audit_logs テーブル（改ざん防止ハッシュチェーン）
    # ─────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        # 改ざん防止チェーンハッシュ（SHA256）
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # インデックス作成（クエリ性能）
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_employee_id", "users", ["employee_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_access_requests_status", "access_requests")
    op.drop_index("ix_audit_logs_created_at", "audit_logs")
    op.drop_index("ix_audit_logs_event_type", "audit_logs")
    op.drop_index("ix_users_employee_id", "users")
    op.drop_index("ix_users_email", "users")

    op.drop_table("audit_logs")
    op.drop_table("access_requests")
    op.drop_table("resources")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("departments")
