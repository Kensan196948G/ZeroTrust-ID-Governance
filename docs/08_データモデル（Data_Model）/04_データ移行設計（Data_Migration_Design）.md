# データ移行設計（Data Migration Design）

| 項目 | 内容 |
|------|------|
| 文書番号 | DM-MIG-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | ZeroTrust-ID-Governance 開発チーム |
| ステータス | 承認済み |

---

## 目次

1. [概要](#概要)
2. [Alembicマイグレーション戦略](#alembicマイグレーション戦略)
3. [マイグレーションファイル命名規則](#マイグレーションファイル命名規則)
4. [適用コマンド](#適用コマンド)
5. [Blue-greenデプロイでの事前適用手順](#blue-greenデプロイでの事前適用手順)
6. [ロールバック手順](#ロールバック手順)
7. [データ整合性確認チェックリスト](#データ整合性確認チェックリスト)
8. [CIでの自動マイグレーション実行](#ciでの自動マイグレーション実行)

---

## 概要

本文書は ZeroTrust-ID-Governance システムにおける Alembic を用いたデータベースマイグレーションの設計方針と運用手順を定義する。

### 設計原則

| 原則 | 内容 |
|------|------|
| 前方互換 | 新旧アプリケーションが同じDBスキーマで動作できるよう設計 |
| 冪等性 | マイグレーションを複数回実行しても結果が同じ |
| ロールバック可能 | 全マイグレーションに `downgrade()` を実装 |
| テスト必須 | CI環境でのマイグレーション自動テストを実施 |
| ダウンタイムなし | Blue-green デプロイと組み合わせゼロダウンタイム実現 |

---

## Alembicマイグレーション戦略

### ディレクトリ構成

```
project/
├── alembic/
│   ├── env.py                    # Alembic 環境設定
│   ├── script.py.mako            # マイグレーションテンプレート
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_add_departments.py
│       ├── 003_add_users.py
│       ├── 004_add_roles.py
│       ├── 005_add_user_roles.py
│       ├── 006_add_access_requests.py
│       ├── 007_add_audit_logs.py
│       └── 008_add_indexes.py
└── alembic.ini
```

### alembic.ini 設定

```ini
[alembic]
script_location = alembic
file_template = %%(rev)s_%%(slug)s
truncate_slug_length = 50
timezone = UTC

# 環境変数から接続URLを取得（本番では直接記述しない）
sqlalchemy.url = %(DATABASE_URL)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### env.py 設定

```python
# alembic/env.py
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.models import Base  # 全モデルのメタデータ

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@localhost/zerotrust_id"
    )

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### マイグレーション方針

| 方針 | 詳細 |
|------|------|
| 単一操作の原則 | 1マイグレーションファイル = 1つの変更目的 |
| 後方互換カラム追加 | `NOT NULL` カラム追加時は DEFAULT を設定し既存レコードを破壊しない |
| 段階的リネーム | カラム名変更は「追加 → データコピー → 削除」の3段階で実施 |
| インデックス分離 | 大規模テーブルへのインデックス追加は `CONCURRENTLY` オプションを使用 |

---

## マイグレーションファイル命名規則

### 命名規則

```
{4桁連番}_{変更内容を簡潔に表す英語スネークケース}.py
```

### 具体例

```
001_initial_schema.py
002_create_departments_table.py
003_create_users_table.py
004_create_roles_table.py
005_create_user_roles_table.py
006_create_access_requests_table.py
007_create_audit_logs_table.py
008_add_indexes_departments.py
009_add_indexes_users.py
010_add_rls_audit_logs.py
011_add_column_users_employee_id.py
012_alter_column_users_full_name_length.py
013_add_table_sessions.py
```

### 自動生成コマンド

```bash
# モデルの変更を自動検出してマイグレーション生成
alembic revision --autogenerate -m "add_column_users_employee_id"
# → alembic/versions/xxxx_add_column_users_employee_id.py が生成される

# 空のマイグレーションファイル生成（手動記述用）
alembic revision -m "add_rls_audit_logs"
```

### マイグレーションファイルのテンプレート

```python
# alembic/versions/011_add_column_users_employee_id.py
"""add_column_users_employee_id

Revision ID: 550ac7e8b3a1
Revises: 449bd6c7f2d0
Create Date: 2026-03-25 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '550ac7e8b3a1'
down_revision = '449bd6c7f2d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """users テーブルに employee_id カラムを追加"""
    op.add_column(
        'users',
        sa.Column(
            'employee_id',
            sa.String(50),
            nullable=True,
            comment='社員番号'
        )
    )
    op.create_unique_constraint(
        'uq_users_employee_id',
        'users',
        ['employee_id']
    )
    op.create_index(
        'idx_users_employee_id',
        'users',
        ['employee_id']
    )


def downgrade() -> None:
    """追加したカラムと制約を削除"""
    op.drop_index('idx_users_employee_id', table_name='users')
    op.drop_constraint('uq_users_employee_id', 'users', type_='unique')
    op.drop_column('users', 'employee_id')
```

---

## 適用コマンド

### 基本コマンド

```bash
# 全マイグレーションを最新に適用
alembic upgrade head

# 1段階だけ適用
alembic upgrade +1

# 特定のリビジョンまで適用
alembic upgrade 550ac7e8b3a1

# 1段階だけロールバック
alembic downgrade -1

# 特定のリビジョンまでロールバック
alembic downgrade 449bd6c7f2d0

# 初期状態に完全ロールバック
alembic downgrade base

# 現在の適用状態を確認
alembic current

# マイグレーション履歴を表示
alembic history --verbose

# 未適用のマイグレーションを確認
alembic history -r current:head

# SQL を生成（適用せずに確認）
alembic upgrade head --sql > migration_preview.sql
```

### 環境別の実行方法

```bash
# 開発環境
DATABASE_URL="postgresql+psycopg2://dev:dev@localhost:5432/zerotrust_id_dev" \
    alembic upgrade head

# ステージング環境
DATABASE_URL=$STAGING_DATABASE_URL alembic upgrade head

# 本番環境（確認プロンプト付きスクリプト経由）
./scripts/migrate_production.sh
```

### 本番マイグレーション安全スクリプト

```bash
#!/usr/bin/env bash
# scripts/migrate_production.sh

set -euo pipefail

echo "=== 本番マイグレーション実行 ==="
echo "現在のリビジョン:"
alembic current

echo ""
echo "適用予定のマイグレーション:"
alembic history -r current:head

echo ""
read -p "続行しますか？ [y/N]: " confirm
if [[ "$confirm" != "y" ]]; then
    echo "キャンセルしました"
    exit 1
fi

# バックアップ確認
echo "DBバックアップが完了していることを確認してください"
read -p "バックアップ完了済みですか？ [y/N]: " backup_confirm
if [[ "$backup_confirm" != "y" ]]; then
    echo "バックアップを先に完了してください"
    exit 1
fi

echo "マイグレーション適用中..."
alembic upgrade head

echo ""
echo "適用完了。現在のリビジョン:"
alembic current
echo "=== マイグレーション完了 ==="
```

---

## Blue-greenデプロイでの事前適用手順

### Blue-green デプロイの概念

```mermaid
flowchart LR
    LB[ロードバランサー] -->|100% トラフィック| BLUE[Blue環境\n旧バージョン]
    LB -.->|0% トラフィック| GREEN[Green環境\n新バージョン]
    BOTH_DB[(共有 PostgreSQL\nデータベース)]
    BLUE --> BOTH_DB
    GREEN --> BOTH_DB
```

### マイグレーション適用フロー

```mermaid
flowchart TD
    START([デプロイ開始]) --> BUILD[Green環境\nビルド・デプロイ準備]
    BUILD --> HEALTH[Green環境\nヘルスチェック通過確認]
    HEALTH --> MIGRATE[マイグレーション適用\nalembic upgrade head]
    MIGRATE --> MIG_CHK{マイグレーション\n成功確認}
    MIG_CHK -->|失敗| ROLLBACK_MIG[マイグレーション\nロールバック]
    ROLLBACK_MIG --> ABORT[デプロイ中止\n障害対応]
    MIG_CHK -->|成功| SMOKE[Green環境\nスモークテスト]
    SMOKE -->|NG| ROLLBACK_MIG
    SMOKE -->|OK| SWITCH[ロードバランサー切替\nBlue → Green へ100%]
    SWITCH --> MONITOR[5〜10分\nモニタリング]
    MONITOR -->|異常検知| ROLLBACK_SWITCH[ロードバランサー\nBlue へ戻す]
    MONITOR -->|正常| DONE[デプロイ完了\nBlue環境を待機状態に]
```

### 前方互換マイグレーションの実装例

Blue-green デプロイでは旧バージョン（Blue）と新バージョン（Green）が一時的に同じDBを参照するため、マイグレーションは前方互換性を維持する必要がある。

```python
# 良い例: NOT NULL カラム追加（前方互換）
def upgrade() -> None:
    # Step 1: NULL 許容でカラム追加（旧アプリがNULLで挿入しても動作する）
    op.add_column('users',
        sa.Column('employee_id', sa.String(50), nullable=True))

    # Step 2: 既存レコードにデフォルト値を設定（必要な場合）
    op.execute("UPDATE users SET employee_id = 'LEGACY-' || id::text WHERE employee_id IS NULL")

    # Step 3: NOT NULL 制約の追加は次のマイグレーションで実施（旧アプリのデプロイ終了後）

# 悪い例: 即座に NOT NULL を追加（旧アプリが対応できない）
def upgrade_bad() -> None:
    op.add_column('users',
        sa.Column('employee_id', sa.String(50), nullable=False))  # 危険！
```

### 段階的なカラム削除手順

```python
# Step 1: 旧カラムを deprecated マーキング（マイグレーション N）
# Step 2: アプリコードから旧カラム参照を削除（デプロイ N+1）
# Step 3: カラム物理削除（マイグレーション N+2, 旧バージョン終了後）

# マイグレーション N+2: 旧カラム削除
def upgrade() -> None:
    op.drop_column('users', 'old_employee_code')  # 旧アプリが参照していないことを確認済み
```

---

## ロールバック手順

### ロールバック判断基準

| 状況 | 対応 |
|------|------|
| マイグレーション途中でエラー | 即時ロールバック |
| マイグレーション後のスモークテスト失敗 | 即時ロールバック |
| デプロイ後 10 分以内のエラー率急増 | 即時ロールバック検討 |
| データ不整合を発見 | ロールバック + 調査 |

### ロールバック手順

```bash
# 1. 現在のリビジョンを確認
alembic current

# 2. ロールバック先のリビジョンを特定
alembic history --verbose

# 3. ロールバック実行
alembic downgrade -1               # 1ステップ戻す
alembic downgrade <revision_id>    # 特定リビジョンまで戻す

# 4. ロールバック確認
alembic current

# 5. アプリケーション再起動（旧バージョンに戻す）
# ロードバランサーを Blue 環境へ切り戻す
```

### ロールバック不可ケースと対処

| ケース | 理由 | 対処 |
|--------|------|------|
| データが既に変換・削除されている | `downgrade()` でデータは復元されない | 最新バックアップからリストア |
| 大量データ移行後 | ロールバックに時間がかかる | 事前にメンテナンス時間を確保 |
| 外部システムが新スキーマに依存 | 外部システムを同時にロールバック必要 | 事前に連携先に通知・調整 |

---

## データ整合性確認チェックリスト

### マイグレーション前チェック

```bash
# チェックリスト 1: バックアップ確認
□ 直近のバックアップが正常に完了しているか
□ バックアップからのリストアテストを最近実施したか
□ バックアップの保存場所と期間を確認したか

# チェックリスト 2: マイグレーション内容確認
□ マイグレーションファイルのレビューが完了しているか
□ downgrade() が実装されているか
□ ステージング環境でテスト済みか
□ 本番 DB のバージョンと整合するか（alembic current で確認）

# チェックリスト 3: 影響範囲確認
□ 変更対象テーブルのレコード数を確認したか
□ 長時間ロックが発生しないか確認したか
□ CONCURRENTLY オプションが必要なインデックス操作はあるか
```

### マイグレーション後チェック

```sql
-- 1. テーブル存在確認
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 2. カラム定義確認
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'users'
ORDER BY ordinal_position;

-- 3. 制約確認
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'public'
  AND table_name = 'users';

-- 4. インデックス確認
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'users';

-- 5. レコード数確認（移行前後の差分チェック）
SELECT
    'departments' AS tbl, COUNT(*) AS cnt FROM departments
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'roles', COUNT(*) FROM roles
UNION ALL SELECT 'user_roles', COUNT(*) FROM user_roles
UNION ALL SELECT 'access_requests', COUNT(*) FROM access_requests
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;

-- 6. Alembic バージョン確認
SELECT version_num FROM alembic_version;

-- 7. FK 整合性確認
SELECT COUNT(*) AS orphan_users
FROM users u
WHERE u.department_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM departments d WHERE d.id = u.department_id
  );
```

### 自動整合性確認スクリプト

```python
#!/usr/bin/env python3
# scripts/verify_migration.py

import asyncio
from sqlalchemy import text
from app.db import AsyncSessionFactory

INTEGRITY_CHECKS = [
    ("孤立ユーザー（部門FK）", """
        SELECT COUNT(*) FROM users u
        WHERE u.department_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM departments d WHERE d.id = u.department_id)
    """),
    ("期限切れアクティブロール", """
        SELECT COUNT(*) FROM user_roles
        WHERE is_active = TRUE AND expires_at IS NOT NULL AND expires_at < NOW()
    """),
    ("UNIQUE制約違反（username）", """
        SELECT COUNT(*) FROM (
            SELECT username FROM users GROUP BY username HAVING COUNT(*) > 1
        ) t
    """),
]

async def verify():
    errors = []
    async with AsyncSessionFactory() as session:
        for name, query in INTEGRITY_CHECKS:
            result = await session.execute(text(query))
            count = result.scalar()
            status = "OK" if count == 0 else f"NG ({count}件)"
            print(f"  {name}: {status}")
            if count > 0:
                errors.append(name)

    if errors:
        print(f"\n整合性エラー: {len(errors)}件")
        raise SystemExit(1)
    else:
        print("\n全整合性チェック OK")

asyncio.run(verify())
```

---

## CIでの自動マイグレーション実行

### GitHub Actions ワークフロー

```yaml
# .github/workflows/migration.yml
name: Database Migration Test

on:
  push:
    branches: [main, develop]
    paths:
      - "alembic/**"
      - "app/models/**"
  pull_request:
    paths:
      - "alembic/**"
      - "app/models/**"

jobs:
  migration-test:
    name: Test DB Migration
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: zerotrust_id_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: postgresql+psycopg2://testuser:testpass@localhost:5432/zerotrust_id_test

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run migrations (upgrade)
        run: alembic upgrade head

      - name: Verify migration (current revision)
        run: alembic current

      - name: Seed test data
        run: python -m app.seeds.run --env=test

      - name: Run integrity checks
        run: python scripts/verify_migration.py

      - name: Test downgrade (rollback test)
        run: |
          alembic downgrade -1
          alembic upgrade head

      - name: Run application tests
        run: pytest tests/ -v --tb=short
```

### デプロイパイプラインでのマイグレーション自動実行

```yaml
# .github/workflows/deploy.yml（一部抜粋）
  deploy-staging:
    name: Deploy to Staging
    needs: [build, migration-test]
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - name: Apply migrations to staging DB
        env:
          DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
        run: |
          echo "=== 現在のリビジョン ==="
          alembic current
          echo "=== マイグレーション適用 ==="
          alembic upgrade head
          echo "=== 適用後リビジョン ==="
          alembic current
          echo "=== 整合性確認 ==="
          python scripts/verify_migration.py

      - name: Deploy application
        # アプリデプロイ処理
        run: ./scripts/deploy.sh staging
```

### マイグレーションの CI 品質ゲート

| チェック項目 | 合否基準 | ブロック条件 |
|-----------|--------|-----------|
| `alembic upgrade head` 成功 | Exit code 0 | 失敗時はデプロイ中止 |
| `alembic downgrade -1` 成功 | Exit code 0 | 失敗時はデプロイ中止 |
| データ整合性チェック | エラー 0件 | エラーあり時はデプロイ中止 |
| 単体テスト・E2Eテスト通過 | 全テスト GREEN | 失敗時はデプロイ中止 |
| マイグレーションファイルのリント | フォーマット準拠 | 非準拠時は警告 |

---

## 改訂履歴

| バージョン | 日付 | 変更内容 | 変更者 |
|----------|------|---------|-------|
| 1.0.0 | 2026-03-25 | 初版作成 | 開発チーム |
