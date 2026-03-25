# 環境構築ガイド（Environment Setup Guide）

| 項目 | 内容 |
|------|------|
| 文書番号 | DEV-ENV-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新 | 2026-03-24 |
| 対象プロジェクト | ZeroTrust-ID-Governance |
| 担当 | 開発チーム |
| ステータス | 有効 |

---

## 目次

1. [前提条件](#1-前提条件)
2. [リポジトリクローン手順](#2-リポジトリクローン手順)
3. [環境変数（.env）設定](#3-環境変数env設定)
4. [Docker Compose による起動](#4-docker-compose-による起動)
5. [バックエンド単体起動（uvicorn）](#5-バックエンド単体起動uvicorn)
6. [フロントエンド単体起動（Next.js）](#6-フロントエンド単体起動nextjs)
7. [初期 DB マイグレーション](#7-初期-db-マイグレーション)
8. [初期データ投入（シードデータ）](#8-初期データ投入シードデータ)
9. [動作確認 URL 一覧](#9-動作確認-url-一覧)

---

## 1. 前提条件

開発環境を構築するには、以下のツールが事前にインストールされている必要があります。

| ツール | 必須バージョン | 確認コマンド | 備考 |
|--------|--------------|-------------|------|
| Docker Desktop | 4.x 以上 | `docker --version` | Linux は Docker Engine 24.x+ |
| Docker Compose | v2.x 以上 | `docker compose version` | `docker-compose`（v1）は非対応 |
| Git | 2.x 以上 | `git --version` | |
| Node.js | 18.x 以上（推奨: 20.x LTS） | `node --version` | フロントエンド開発時のみ |
| npm | 9.x 以上 | `npm --version` | Node.js に同梱 |
| Python | 3.11.x 以上 | `python3 --version` | バックエンド単体開発時のみ |
| pip / uv | 最新 | `pip --version` / `uv --version` | 依存パッケージ管理 |
| Make | 任意 | `make --version` | Makefile タスク実行時 |

### インストール確認

```bash
# 各ツールのバージョン一括確認
docker --version
docker compose version
git --version
node --version
npm --version
python3 --version
```

---

## 2. リポジトリクローン手順

### 2.1 リポジトリのクローン

```bash
# SSH（推奨）
git clone git@github.com:your-org/ZeroTrust-ID-Governance.git

# HTTPS
git clone https://github.com/your-org/ZeroTrust-ID-Governance.git

# クローン先ディレクトリへ移動
cd ZeroTrust-ID-Governance
```

### 2.2 ブランチ確認

```bash
# 現在のブランチ確認
git branch -a

# 開発ブランチへ切り替え（必要に応じて）
git checkout develop
```

### 2.3 サブモジュール初期化（存在する場合）

```bash
git submodule update --init --recursive
```

---

## 3. 環境変数（.env）設定

### 3.1 テンプレートからコピー

```bash
# バックエンド用
cp backend/.env.example backend/.env

# フロントエンド用
cp frontend/.env.example frontend/.env.local

# Docker Compose 用（ルートディレクトリ）
cp .env.example .env
```

### 3.2 バックエンド環境変数一覧（`backend/.env`）

| 変数名 | 例 | 説明 | 必須 |
|--------|----|------|------|
| `APP_ENV` | `development` | 実行環境（development/staging/production） | 必須 |
| `APP_NAME` | `ZeroTrust-ID-Governance` | アプリケーション名 | 必須 |
| `APP_VERSION` | `1.0.0` | アプリケーションバージョン | 任意 |
| `DATABASE_URL` | `postgresql+asyncpg://ztid:password@localhost:5432/ztid_db` | PostgreSQL 接続 URL | 必須 |
| `DATABASE_TEST_URL` | `postgresql+asyncpg://ztid:password@localhost:5432/ztid_test_db` | テスト用 DB URL | テスト時必須 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 接続 URL | 必須 |
| `REDIS_CACHE_DB` | `1` | Redis キャッシュ用 DB インデックス | 任意 |
| `JWT_SECRET_KEY` | `your-super-secret-key-change-in-production` | JWT 署名シークレット（64文字以上推奨） | 必須 |
| `JWT_ALGORITHM` | `HS256` | JWT アルゴリズム | 必須 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | アクセストークン有効期限（分） | 必須 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | リフレッシュトークン有効期限（日） | 必須 |
| `CORS_ORIGINS` | `http://localhost:3000` | 許可する CORS オリジン（カンマ区切り） | 必須 |
| `CELERY_BROKER_URL` | `redis://localhost:6379/2` | Celery ブローカー URL | 必須 |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/3` | Celery 結果バックエンド | 必須 |
| `LOG_LEVEL` | `DEBUG` | ログレベル（DEBUG/INFO/WARNING/ERROR） | 任意 |
| `SECRET_KEY` | `your-secret-key-for-sessions` | セッション用シークレット | 必須 |

```bash
# backend/.env の記述例
APP_ENV=development
APP_NAME=ZeroTrust-ID-Governance
APP_VERSION=1.0.0

# Database
DATABASE_URL=postgresql+asyncpg://ztid:ztid_password@localhost:5432/ztid_db
DATABASE_TEST_URL=postgresql+asyncpg://ztid:ztid_password@localhost:5432/ztid_test_db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_DB=1

# JWT
JWT_SECRET_KEY=change-this-secret-key-to-something-very-long-and-random
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Celery
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/3

# Logging
LOG_LEVEL=DEBUG
```

### 3.3 フロントエンド環境変数一覧（`frontend/.env.local`）

| 変数名 | 例 | 説明 |
|--------|----|------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | バックエンド API の URL |
| `NEXT_PUBLIC_APP_NAME` | `ZeroTrust ID Governance` | アプリケーション表示名 |
| `NEXTAUTH_SECRET` | `your-nextauth-secret` | NextAuth.js シークレット |
| `NEXTAUTH_URL` | `http://localhost:3000` | NextAuth.js コールバック URL |

```bash
# frontend/.env.local の記述例
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=ZeroTrust ID Governance
NEXTAUTH_SECRET=your-nextauth-secret-key
NEXTAUTH_URL=http://localhost:3000
```

### 3.4 セキュリティ注意事項

> **警告**: `.env` ファイルには機密情報が含まれます。`.gitignore` に必ず追加され、リポジトリにコミットしないでください。

```bash
# .gitignore に含まれていることを確認
grep -n "\.env" .gitignore
```

---

## 4. Docker Compose による起動

### 4.1 全サービス起動

```bash
# ルートディレクトリで実行
# バックグラウンドで全サービスを起動
docker compose up -d

# ログを確認しながら起動（フォアグラウンド）
docker compose up
```

### 4.2 Docker Compose サービス構成

| サービス名 | イメージ | ポート | 説明 |
|-----------|---------|--------|------|
| `backend` | `./backend` (custom) | `8000:8000` | FastAPI バックエンド |
| `frontend` | `./frontend` (custom) | `3000:3000` | Next.js フロントエンド |
| `db` | `postgres:16-alpine` | `5432:5432` | PostgreSQL データベース |
| `redis` | `redis:7-alpine` | `6379:6379` | Redis キャッシュ/Pub-Sub |
| `celery_worker` | `./backend` (custom) | なし | Celery 非同期ワーカー |
| `celery_beat` | `./backend` (custom) | なし | Celery スケジューラ |

### 4.3 サービスの状態確認

```bash
# サービス一覧と状態確認
docker compose ps

# 特定サービスのログ確認
docker compose logs -f backend
docker compose logs -f db
docker compose logs -f redis

# 全サービスのログ確認
docker compose logs -f
```

### 4.4 サービスの停止・削除

```bash
# サービスを停止（コンテナを保持）
docker compose stop

# サービスを停止し、コンテナを削除
docker compose down

# ボリュームも含めて完全削除（データリセット時）
docker compose down -v
```

### 4.5 特定サービスのみ再起動

```bash
# バックエンドのみ再ビルド・再起動
docker compose up -d --build backend

# DB とバックエンドのみ起動
docker compose up -d db redis backend
```

---

## 5. バックエンド単体起動（uvicorn）

Docker を使わずにバックエンドをローカルで直接起動する手順です。事前に PostgreSQL と Redis が起動している必要があります。

### 5.1 Python 仮想環境の作成

```bash
cd backend

# venv を使用する場合
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# uv を使用する場合（推奨）
uv venv --python 3.11
source .venv/bin/activate
```

### 5.2 依存パッケージのインストール

```bash
# pip を使用する場合
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 開発用パッケージ

# uv を使用する場合（推奨・高速）
uv pip sync requirements.txt requirements-dev.txt
```

### 5.3 uvicorn での起動

```bash
# 開発モード（ホットリロード有効）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ログレベルを指定して起動
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# 本番相当（ワーカー数指定）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5.4 Celery ワーカー起動（別ターミナル）

```bash
# Celery ワーカー起動
celery -A app.celery_app worker --loglevel=info

# Celery Beat（スケジューラ）起動
celery -A app.celery_app beat --loglevel=info
```

---

## 6. フロントエンド単体起動（Next.js）

### 6.1 依存パッケージのインストール

```bash
cd frontend

# npm を使用する場合
npm install

# 依存関係の監査（セキュリティチェック）
npm audit
```

### 6.2 開発サーバーの起動

```bash
# 開発モード（ホットリロード有効）
npm run dev

# 特定ポートで起動
npm run dev -- --port 3001

# ホストを指定して起動（外部からアクセス可能）
npm run dev -- --hostname 0.0.0.0
```

### 6.3 ビルドと本番起動

```bash
# 本番ビルド
npm run build

# ビルド結果の確認
npm run start

# 型チェック
npm run type-check

# Lint チェック
npm run lint
```

---

## 7. 初期 DB マイグレーション

### 7.1 Alembic の設定確認

```bash
cd backend

# Alembic の設定ファイル確認
cat alembic.ini

# 現在のマイグレーション状態確認
alembic current

# マイグレーション履歴確認
alembic history --verbose
```

### 7.2 マイグレーションの適用

```bash
# 最新マイグレーションを適用
alembic upgrade head

# 特定リビジョンまで適用
alembic upgrade <revision_id>

# 1つ前のリビジョンに戻す
alembic downgrade -1

# 最初の状態に戻す
alembic downgrade base
```

### 7.3 Docker Compose 環境でのマイグレーション

```bash
# Docker コンテナ内でマイグレーション実行
docker compose exec backend alembic upgrade head

# マイグレーション状態確認
docker compose exec backend alembic current
```

### 7.4 新しいマイグレーションファイルの作成

```bash
# モデル変更後に自動生成
alembic revision --autogenerate -m "add_user_table"

# 空のマイグレーションファイルを作成
alembic revision -m "custom_migration"
```

---

## 8. 初期データ投入（シードデータ）

### 8.1 シードスクリプトの実行

```bash
cd backend

# ローカル環境でシードデータを投入
python -m scripts.seed_data

# または Make コマンドを使用
make seed

# Docker 環境での実行
docker compose exec backend python -m scripts.seed_data
```

### 8.2 シードデータの内容

| データ種別 | 説明 | 件数（初期） |
|-----------|------|------------|
| 管理者ユーザー | システム管理者アカウント | 1件 |
| ロール定義 | admin / manager / operator / viewer | 4件 |
| 権限定義 | RBAC パーミッション一式 | 約50件 |
| 組織定義 | デフォルト組織 | 1件 |
| テストユーザー | 開発・テスト用ユーザー | 5件 |

### 8.3 初期管理者アカウント

> **重要**: 初回ログイン後、必ずパスワードを変更してください。

| 項目 | 値 |
|------|----|
| メールアドレス | `admin@example.com` |
| 初期パスワード | `Admin@12345!` |
| ロール | `admin` |

```bash
# 管理者パスワードの変更（CLI から）
docker compose exec backend python -m scripts.change_password \
  --email admin@example.com \
  --new-password "YourNewSecurePassword!"
```

---

## 9. 動作確認 URL 一覧

### 9.1 主要アクセス URL

| サービス | URL | 説明 | 認証 |
|---------|-----|------|------|
| フロントエンド | `http://localhost:3000` | Next.js アプリケーション | - |
| API ドキュメント（Swagger UI） | `http://localhost:8000/docs` | FastAPI 自動生成 API ドキュメント | - |
| API ドキュメント（ReDoc） | `http://localhost:8000/redoc` | 代替 API ドキュメント | - |
| ヘルスチェック | `http://localhost:8000/health` | アプリケーション死活確認 | 不要 |
| メトリクス | `http://localhost:8000/metrics` | Prometheus メトリクス | 任意 |
| DB（pgAdmin） | `http://localhost:5050` | PostgreSQL 管理 UI（要追加設定） | 要設定 |
| Redis（RedisInsight） | `http://localhost:8001` | Redis 管理 UI（要追加設定） | - |

### 9.2 API ヘルスチェック

```bash
# ヘルスチェック
curl http://localhost:8000/health

# 期待されるレスポンス
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "version": "1.0.0"
# }
```

### 9.3 初回ログイン確認

```bash
# JWT トークン取得
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin@12345!"}'

# 取得したトークンで認証確認
TOKEN="<上記で取得した access_token>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/me
```

### 9.4 Docker ネットワーク内サービス URL

Docker Compose 環境内のサービス間通信では以下の URL を使用します。

| サービス | 内部 URL |
|---------|---------|
| バックエンド | `http://backend:8000` |
| PostgreSQL | `postgresql://db:5432` |
| Redis | `redis://redis:6379` |

---

## 付録：よく使うコマンド集

```bash
# 全サービス起動
docker compose up -d

# ログ確認
docker compose logs -f backend

# マイグレーション適用
docker compose exec backend alembic upgrade head

# シードデータ投入
docker compose exec backend python -m scripts.seed_data

# バックエンドシェルに入る
docker compose exec backend bash

# DB に接続
docker compose exec db psql -U ztid -d ztid_db

# Redis CLI
docker compose exec redis redis-cli

# テスト実行
docker compose exec backend pytest

# フロントエンド Lint
docker compose exec frontend npm run lint
```

---

*文書番号: DEV-ENV-001 | バージョン: 1.0.0 | 最終更新: 2026-03-24*
