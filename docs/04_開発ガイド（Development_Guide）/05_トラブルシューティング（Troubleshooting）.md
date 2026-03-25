# トラブルシューティングガイド（Troubleshooting Guide）

| 項目 | 内容 |
|------|------|
| 文書番号 | DEV-TRB-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新 | 2026-03-24 |
| 対象プロジェクト | ZeroTrust-ID-Governance |
| 担当 | 開発チーム / SRE チーム |
| ステータス | 有効 |

---

## 目次

1. [よくある問題と解決策](#1-よくある問題と解決策)
2. [ログの確認方法](#2-ログの確認方法)
3. [デバッグモード起動方法](#3-デバッグモード起動方法)
4. [環境変数チェックリスト](#4-環境変数チェックリスト)

---

## 1. よくある問題と解決策

### 1.1 DB 接続エラー

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `sqlalchemy.exc.OperationalError: could not connect to server` | PostgreSQL が起動していない | `docker compose up -d db` で DB を起動 |
| `FATAL: password authentication failed for user "ztid"` | パスワードが間違っている | `.env` の `DATABASE_URL` のパスワードを確認 |
| `FATAL: database "ztid_db" does not exist` | DB が作成されていない | `docker compose exec db createdb -U ztid ztid_db` |
| `could not translate host name "db" to address` | Docker ネットワーク未接続 | `docker compose down && docker compose up -d` |
| `connection pool exhausted` | DB 接続プールが枯渇 | `DATABASE_POOL_SIZE` を増やす、または接続をリリースしているか確認 |
| `SSL connection required` | 本番 DB が SSL 必須 | `DATABASE_URL` に `?sslmode=require` を追加 |

```bash
# DB 接続確認コマンド
docker compose exec db psql -U ztid -d ztid_db -c "SELECT 1;"

# 接続プール状態確認
docker compose exec db psql -U ztid -d ztid_db \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# DB コンテナのログ確認
docker compose logs db --tail=50

# DB コンテナへの接続テスト（バックエンドコンテナから）
docker compose exec backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os

async def test():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print('DB connection OK:', result.scalar())

asyncio.run(test())
"
```

---

### 1.2 JWT 認証エラー

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `401 Unauthorized: Could not validate credentials` | トークンが無効・期限切れ | トークンを再取得（ログイン API を再実行） |
| `401: Signature verification failed` | `JWT_SECRET_KEY` が環境間で異なる | 全環境で同一の `JWT_SECRET_KEY` を使用 |
| `401: Token has expired` | アクセストークンの有効期限切れ | リフレッシュトークンで更新、または再ログイン |
| `403 Forbidden: Insufficient permissions` | ロール・権限が不足 | ユーザーのロール割り当てを確認 |
| `400: Invalid token format` | `Bearer ` プレフィックス漏れ | ヘッダーを `Authorization: Bearer <token>` に修正 |
| `422: Field required: authorization` | Authorization ヘッダーなし | リクエストヘッダーに `Authorization` を追加 |

```bash
# JWT トークンのデコード確認（ローカルで検証）
python3 -c "
import jwt
import os

token = 'YOUR_JWT_TOKEN_HERE'
secret = os.environ.get('JWT_SECRET_KEY', 'your-secret-key')

try:
    payload = jwt.decode(token, secret, algorithms=['HS256'])
    print('Token payload:', payload)
except jwt.ExpiredSignatureError:
    print('ERROR: Token has expired')
except jwt.InvalidSignatureError:
    print('ERROR: Invalid signature - check JWT_SECRET_KEY')
except jwt.DecodeError as e:
    print(f'ERROR: Decode error - {e}')
"

# トークン取得テスト
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin@12345!"}' \
  | python3 -m json.tool

# 認証付きリクエストのテスト
TOKEN="YOUR_ACCESS_TOKEN"
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/me \
  | python3 -m json.tool
```

---

### 1.3 CORS エラー

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `Access to fetch at '...' has been blocked by CORS policy` | CORS オリジンが許可されていない | `CORS_ORIGINS` にフロントエンドの URL を追加 |
| `No 'Access-Control-Allow-Origin' header is present` | バックエンドが CORS ヘッダーを返していない | FastAPI の CORSMiddleware 設定を確認 |
| `Response to preflight request doesn't pass access control check` | OPTIONS メソッドが許可されていない | `allow_methods=["*"]` を設定 |
| CORS エラーが開発時のみ発生 | フロントエンドとバックエンドのポートが異なる | `.env` の `CORS_ORIGINS` に開発用 URL を追加 |

```python
# backend/app/main.py の CORS 設定確認
from fastapi.middleware.cors import CORSMiddleware

# 設定例
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```bash
# CORS ヘッダーの確認
curl -v \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -X OPTIONS \
  http://localhost:8000/api/v1/users

# 期待されるレスポンスヘッダー
# access-control-allow-origin: http://localhost:3000
# access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
# access-control-allow-credentials: true
```

---

### 1.4 Alembic マイグレーション失敗

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `alembic.util.exc.CommandError: Can't locate revision identified by '...'` | マイグレーションファイルが欠落 | `git pull` で最新ファイルを取得 |
| `sqlalchemy.exc.ProgrammingError: column already exists` | 同じマイグレーションが二重適用 | `alembic current` で状態確認後、手動で修正 |
| `Target database is not up to date` | マイグレーション未適用 | `alembic upgrade head` を実行 |
| `ERROR: relation "xxx" does not exist` | テーブルが存在しない | `alembic upgrade head` でテーブルを作成 |
| `Multiple head revisions are present` | ブランチが分岐している | `alembic merge heads` でマージ |
| `alembic.util.exc.CommandError: No such revision` | リビジョン ID が不正 | `alembic history` で有効なリビジョンを確認 |

```bash
# マイグレーション状態の確認
alembic current
alembic history --verbose

# 複数 head の確認
alembic heads

# head がマージされていない場合の対処
alembic merge heads -m "merge_branches"
alembic upgrade head

# マイグレーションのダウングレード（1ステップ戻す）
alembic downgrade -1

# 全テーブルを削除してゼロから作り直す（開発環境のみ）
docker compose exec db psql -U ztid -d ztid_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head

# Docker 環境でのマイグレーション確認
docker compose exec backend alembic current
docker compose exec backend alembic history
```

---

### 1.5 Redis 接続エラー

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `redis.exceptions.ConnectionError: Error connecting to Redis` | Redis が起動していない | `docker compose up -d redis` |
| `WRONGPASS invalid username-password pair` | Redis のパスワードが間違っている | `REDIS_URL` のパスワードを確認 |
| `ConnectionRefusedError: [Errno 111]` | Redis のポートが解放されていない | `REDIS_URL` のポート番号を確認 |
| `redis.exceptions.ResponseError: LOADING Redis is loading` | Redis が起動中（起動直後） | 数秒待ってから再試行 |
| `redis.exceptions.TimeoutError` | Redis 応答タイムアウト | Redis のメモリ使用量・CPU を確認 |
| Celery タスクがキューに溜まる | Redis ブローカーへの接続問題 | `CELERY_BROKER_URL` の確認 |

```bash
# Redis 接続確認
docker compose exec redis redis-cli ping
# 期待値: PONG

# Redis の状態確認
docker compose exec redis redis-cli info server | grep redis_version
docker compose exec redis redis-cli info memory | grep used_memory_human

# キーの確認
docker compose exec redis redis-cli keys "*"
docker compose exec redis redis-cli dbsize

# Celery ブローカーのキュー確認
docker compose exec redis redis-cli llen celery

# Redis のログ確認
docker compose logs redis --tail=50

# Python から Redis 接続テスト
docker compose exec backend python -c "
import redis
import os

r = redis.from_url(os.environ['REDIS_URL'])
print('Redis ping:', r.ping())
print('Redis info:', r.info()['redis_version'])
"
```

---

### 1.6 Docker コンテナ起動失敗

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `Error: No such container` | コンテナが作成されていない | `docker compose up -d` で再作成 |
| `port is already allocated` | ポートが使用中 | `lsof -i :8000` で使用プロセスを確認・停止 |
| `Exit 1` または `Exit 137` | アプリケーションクラッシュ | `docker compose logs <service>` でエラーを確認 |
| `Exit 137` (OOM Killed) | メモリ不足 | Docker のメモリ割り当てを増やす |
| イメージが古い | キャッシュされた古いイメージを使用 | `docker compose build --no-cache` |
| `ENOENT: no such file or directory` | ボリュームマウントのパスが不正 | `docker compose.yml` のマウントパスを確認 |
| `network not found` | Docker ネットワークが削除済み | `docker compose down && docker compose up -d` |

```bash
# コンテナの状態確認
docker compose ps -a

# 停止したコンテナのログ確認
docker compose logs backend --tail=100

# コンテナを強制削除して再作成
docker compose down
docker compose up -d

# イメージを再ビルドして起動
docker compose up -d --build

# ポート使用状況の確認
sudo lsof -i :8000
sudo lsof -i :5432
sudo lsof -i :6379
sudo lsof -i :3000

# Docker リソースの確認
docker system df
docker system prune  # 未使用リソースを削除（注意: ボリューム以外）

# ボリュームを含む完全クリーンアップ（データリセット）
docker compose down -v
docker system prune -a
docker compose up -d
```

---

### 1.7 CI 失敗

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `ruff check` 失敗 | コードスタイル違反 | `ruff check --fix` で自動修正 |
| `mypy` 型チェック失敗 | 型ヒントエラー | エラーメッセージを確認して型アノテーションを修正 |
| `pytest` 失敗 | テスト失敗 | ローカルで `pytest -v` を実行して原因を特定 |
| CI でのみテスト失敗 | 環境変数・依存サービスの差異 | CI の環境変数設定と `services:` ブロックを確認 |
| Docker ビルド失敗 | Dockerfile のエラー | ローカルで `docker build` を実行してエラーを確認 |
| カバレッジ不足 | テストカバレッジが 80% 未満 | カバレッジレポートで未テスト行を確認して追加 |
| Trivy スキャン失敗 | 脆弱性が検出された | 脆弱なパッケージを最新版にアップデート |
| GitHub Actions タイムアウト | テストや処理が遅い | タイムアウト設定を延長、または処理を最適化 |

```bash
# ローカルで CI チェックを再現
# Lint チェック
ruff check backend/
ruff format --check backend/

# 型チェック
mypy backend/

# テスト実行（CI と同じオプション）
pytest --cov=app --cov-fail-under=80 -v

# セキュリティチェック
bandit -r backend/app/
pip-audit

# Trivy スキャン（ローカル）
trivy image --severity CRITICAL,HIGH ztid-backend:latest

# GitHub Actions のワークフローをローカルで実行（act を使用）
act push --workflows .github/workflows/ci.yml
```

---

### 1.8 Celery タスク失敗

| 症状 | 原因 | 解決策 |
|------|------|--------|
| タスクが実行されない | Celery ワーカーが起動していない | `docker compose up -d celery_worker` |
| タスクが PENDING のまま | ブローカー（Redis）への接続失敗 | `CELERY_BROKER_URL` を確認 |
| `Task raised exception: ImportError` | モジュールが見つからない | `PYTHONPATH` の設定を確認 |
| タスクがタイムアウト | 処理時間が長すぎる | `task_time_limit` を設定または処理を最適化 |
| `ConnectionResetError` | ブローカー接続が切れた | Redis の接続設定・タイムアウトを確認 |
| Celery Beat が動作しない | Beat スケジューラが起動していない | `docker compose up -d celery_beat` |

```bash
# Celery ワーカーの状態確認
docker compose exec celery_worker celery -A app.celery_app inspect active

# キュー内のタスク確認
docker compose exec celery_worker celery -A app.celery_app inspect reserved

# Celery ワーカーのログ確認
docker compose logs celery_worker --tail=100 -f

# タスクを手動で実行
docker compose exec backend python -c "
from app.celery_app import celery_app
from app.tasks.email import send_verification_email

result = send_verification_email.delay('user@example.com', 'token123')
print('Task ID:', result.id)
print('Task status:', result.status)
"

# Flower（Celery モニタリング UI）を起動
docker compose exec celery_worker celery -A app.celery_app flower --port=5555
# → http://localhost:5555 でアクセス

# Celery Beat のログ確認
docker compose logs celery_beat --tail=50
```

---

## 2. ログの確認方法

### 2.1 Docker Compose 環境でのログ確認

```bash
# 全サービスのログをリアルタイム表示
docker compose logs -f

# 特定サービスのログ（最新100行）
docker compose logs backend --tail=100
docker compose logs db --tail=100
docker compose logs redis --tail=50

# 特定サービスのログをリアルタイム追跡
docker compose logs -f backend

# タイムスタンプ付きで表示
docker compose logs -t backend

# 複数サービスの同時確認
docker compose logs -f backend celery_worker

# エラーのみフィルタリング
docker compose logs backend 2>&1 | grep -i "error\|exception\|critical"
```

### 2.2 Kubernetes 環境でのログ確認

```bash
# Pod の一覧確認
kubectl get pods -n ztid-production

# 特定 Pod のログ（最新100行）
kubectl logs <pod-name> -n ztid-production --tail=100

# Deployment のログ（全 Pod）
kubectl logs deployment/ztid-backend -n ztid-production --tail=100

# リアルタイムでログを追跡
kubectl logs -f deployment/ztid-backend -n ztid-production

# 前回クラッシュしたコンテナのログ
kubectl logs <pod-name> -n ztid-production --previous

# 複数コンテナがある場合のコンテナ指定
kubectl logs <pod-name> -c backend -n ztid-production

# 時間でフィルタリング（直近1時間）
kubectl logs deployment/ztid-backend -n ztid-production --since=1h
```

### 2.3 アプリケーションログの構造

```json
// 構造化ログの例（JSON 形式）
{
  "timestamp": "2026-03-24T10:30:00.000Z",
  "level": "ERROR",
  "logger": "app.services.auth",
  "message": "Login failed: invalid credentials",
  "request_id": "req-abc123",
  "user_email": "user@example.com",
  "ip_address": "192.168.1.1",
  "path": "/api/v1/auth/login",
  "method": "POST",
  "status_code": 401,
  "duration_ms": 125
}
```

### 2.4 ログレベルの確認

| レベル | 説明 | 対応優先度 |
|--------|------|----------|
| `CRITICAL` | システム停止レベルのエラー | 即時対応 |
| `ERROR` | 処理が失敗したエラー | 早急に対応 |
| `WARNING` | 注意が必要な状況 | 監視・確認 |
| `INFO` | 通常の動作ログ | 確認不要 |
| `DEBUG` | デバッグ情報 | 開発時のみ |

```bash
# エラーログのみフィルタリング（Docker）
docker compose logs backend | grep '"level": "ERROR"'

# ログをファイルに保存
docker compose logs backend > backend_logs_$(date +%Y%m%d).log

# JSON ログをパース（jq を使用）
docker compose logs backend | grep '^{' | jq 'select(.level == "ERROR")'
```

---

## 3. デバッグモード起動方法

### 3.1 バックエンドのデバッグモード

```bash
# デバッグログを有効にして起動
LOG_LEVEL=DEBUG uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Python デバッガー（pdb）を挿入してデバッグ
# コード内に以下を追加
import pdb; pdb.set_trace()

# または debugpy（VS Code リモートデバッグ）を使用
# pip install debugpy
import debugpy
debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()  # VS Code からアタッチするまで待機
```

```yaml
# docker-compose.override.yml（デバッグ用）
services:
  backend:
    environment:
      - LOG_LEVEL=DEBUG
      - APP_ENV=development
    ports:
      - "5678:5678"  # debugpy ポート
    volumes:
      - ./backend:/app  # ホットリロード用ボリュームマウント
    command: >
      python -m debugpy --listen 0.0.0.0:5678
      -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.2 FastAPI のデバッグ設定

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def set_debug_mode(self) -> "Settings":
        if self.APP_ENV == "development":
            self.DEBUG = True
            self.LOG_LEVEL = "DEBUG"
        return self

# backend/app/main.py
app = FastAPI(
    debug=settings.DEBUG,
    # DEBUG=True の場合、詳細なエラートレースバックを返す
)
```

### 3.3 SQL クエリのデバッグ（SQLAlchemy）

```python
# クエリログを有効化
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# または環境変数で設定
# SQLALCHEMY_ECHO=true
```

```bash
# Docker 環境でクエリログを有効化
docker compose exec backend bash -c "
  SQLALCHEMY_ECHO=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"
```

### 3.4 フロントエンドのデバッグモード

```bash
# Next.js デバッグモード
NODE_OPTIONS='--inspect' npm run dev
# → chrome://inspect でブラウザデバッガーに接続

# 詳細ログを有効化
DEBUG=* npm run dev

# React DevTools の有効化（ブラウザ拡張機能のインストール推奨）
REACT_EDITOR=vscode npm run dev
```

### 3.5 API リクエストのデバッグ

```bash
# curl で詳細デバッグ情報を表示
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Admin@12345!"}'

# httpie（curl の代替、より見やすい出力）を使用
pip install httpie
http POST http://localhost:8000/api/v1/auth/login \
  email=admin@example.com password=Admin@12345!

# Swagger UI でインタラクティブにテスト
# → http://localhost:8000/docs
```

---

## 4. 環境変数チェックリスト

### 4.1 必須環境変数チェックリスト

以下のコマンドで環境変数が正しく設定されているか確認します。

```bash
# Docker コンテナ内の環境変数確認
docker compose exec backend env | sort

# 特定の環境変数を確認
docker compose exec backend printenv DATABASE_URL
docker compose exec backend printenv JWT_SECRET_KEY
docker compose exec backend printenv REDIS_URL
```

### 4.2 バックエンド環境変数チェックリスト

| カテゴリ | 変数名 | 確認コマンド | チェック内容 |
|---------|--------|------------|------------|
| **アプリ** | `APP_ENV` | `printenv APP_ENV` | `development` / `staging` / `production` のいずれか |
| **DB** | `DATABASE_URL` | `printenv DATABASE_URL` | `postgresql+asyncpg://` で始まること |
| **DB** | `DATABASE_URL` | 接続テスト | DB への接続が成功すること |
| **Redis** | `REDIS_URL` | `printenv REDIS_URL` | `redis://` で始まること |
| **Redis** | `REDIS_URL` | `redis-cli ping` | `PONG` が返ること |
| **JWT** | `JWT_SECRET_KEY` | 長さ確認 | 32文字以上であること |
| **JWT** | `JWT_ALGORITHM` | `printenv JWT_ALGORITHM` | `HS256` または `RS256` |
| **JWT** | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 値確認 | 1〜1440 の整数値 |
| **CORS** | `CORS_ORIGINS` | `printenv CORS_ORIGINS` | フロントエンドの URL が含まれること |
| **Celery** | `CELERY_BROKER_URL` | `printenv CELERY_BROKER_URL` | `redis://` で始まること |

### 4.3 環境変数の一括確認スクリプト

```bash
# backend/.env の検証スクリプト
docker compose exec backend python -c "
from app.core.config import settings
import sys

errors = []

# DB URL の形式確認
if not settings.DATABASE_URL.startswith('postgresql'):
    errors.append('ERROR: DATABASE_URL must start with postgresql')

# JWT シークレットの長さ確認
if len(settings.JWT_SECRET_KEY) < 32:
    errors.append('ERROR: JWT_SECRET_KEY must be at least 32 characters')

# CORS オリジンの確認
if not settings.CORS_ORIGINS:
    errors.append('ERROR: CORS_ORIGINS must not be empty')

# Redis URL の形式確認
if not settings.REDIS_URL.startswith('redis'):
    errors.append('ERROR: REDIS_URL must start with redis')

if errors:
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print('All environment variables are valid.')
"
```

### 4.4 本番環境デプロイ前の環境変数チェック

| 変数 | 開発環境 | 本番環境での注意点 |
|------|---------|-----------------|
| `APP_ENV` | `development` | `production` に変更必須 |
| `JWT_SECRET_KEY` | ローカル用任意の値 | 安全なランダム文字列（64文字以上）に変更必須 |
| `DATABASE_URL` | ローカル DB | 本番 DB URL に変更必須 |
| `CORS_ORIGINS` | `http://localhost:3000` | 本番フロントエンド URL に変更必須 |
| `LOG_LEVEL` | `DEBUG` | `INFO` または `WARNING` に変更推奨 |
| `SECRET_KEY` | ローカル用任意の値 | 安全なランダム文字列に変更必須 |

```bash
# 安全なシークレットキーの生成方法
python3 -c "import secrets; print(secrets.token_hex(64))"
# または
openssl rand -hex 64
```

### 4.5 環境変数が読み込まれない場合の対処

```bash
# .env ファイルの存在確認
ls -la backend/.env
ls -la frontend/.env.local

# .env ファイルの文字コード確認（BOM なし UTF-8 であること）
file backend/.env

# 改行コードの確認（LF であること）
cat -A backend/.env | head -5
# Windows の CR+LF が混入している場合
sed -i 's/\r//' backend/.env

# Docker Compose での .env ファイル確認
docker compose config | grep -A5 "environment:"

# 環境変数が上書きされていないか確認
docker compose exec backend env | grep -E "DATABASE_URL|REDIS_URL|JWT_"
```

---

## 付録：エラーコード一覧

| HTTP ステータス | エラーコード | 説明 | 対処 |
|--------------|-----------|------|------|
| `400` | `INVALID_REQUEST` | リクエストパラメータが不正 | リクエストボディ・パラメータを確認 |
| `401` | `INVALID_CREDENTIALS` | 認証情報が不正 | メールアドレス・パスワードを確認 |
| `401` | `TOKEN_EXPIRED` | トークン有効期限切れ | トークンを再取得 |
| `401` | `TOKEN_INVALID` | トークンが無効 | 再ログインして新しいトークンを取得 |
| `403` | `INSUFFICIENT_PERMISSIONS` | 権限不足 | 管理者にロール付与を依頼 |
| `404` | `NOT_FOUND` | リソースが存在しない | ID・URL を確認 |
| `409` | `ALREADY_EXISTS` | リソースが既に存在する | 重複データがないか確認 |
| `422` | `VALIDATION_ERROR` | バリデーションエラー | リクエストデータの形式を確認 |
| `429` | `RATE_LIMIT_EXCEEDED` | レート制限に達した | しばらく待ってから再試行 |
| `500` | `INTERNAL_ERROR` | サーバー内部エラー | サーバーログを確認 |
| `503` | `SERVICE_UNAVAILABLE` | サービス停止中 | ヘルスチェックエンドポイントを確認 |

---

*文書番号: DEV-TRB-001 | バージョン: 1.0.0 | 最終更新: 2026-03-24*
