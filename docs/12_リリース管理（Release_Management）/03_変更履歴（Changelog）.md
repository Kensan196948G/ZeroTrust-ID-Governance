# 変更履歴（Changelog）

| 項目 | 内容 |
|------|------|
| **文書番号** | REL-CLOG-001 |
| **バージョン** | 1.0.0 |
| **作成日** | 2026-03-25 |
| **形式** | Keep a Changelog 1.0.0 |

> このドキュメントは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) 形式に従います。
> バージョニングは [Semantic Versioning](https://semver.org/lang/ja/) に準拠します。

---

## [Unreleased]

### Added
- ドキュメント体系（12フォルダ・59ファイル）の包括的整備
- GitHub Projects による開発司令盤の構築
- ClaudeOS v4 自律開発フレームワークの統合

---

## [0.15.0] - 2026-03-25

### Added
- **E2Eテスト基盤**: Playwright によるフロントエンド E2E テスト（認証・ナビゲーション・ページ遷移）
- **Newman API テスト**: バックエンド API の Postman/Newman コレクション（全エンドポイント網羅）
- **CI パイプライン強化**: E2E テストを GitHub Actions に統合
- **テスト専用ログインエンドポイント**: 開発・テスト環境限定の `POST /auth/test-login`
- Phase 15 Issue #34 対応

### Changed
- `claudeos-ci.yml`: E2E テストジョブ追加（backend-e2e, frontend-e2e）
- Newman インストール手順の最適化（不要パッケージ除去）

### Fixed
- Newman 実行時の `newman-reporter-junit` パッケージ不存在エラー修正

---

## [0.14.0] - 2026-03-24

### Added
- **セキュリティヘッダーミドルウェア**: HSTS / CSP / X-Frame-Options / X-Content-Type-Options 等 15項目
- **レート制限ミドルウェア**: IP別・エンドポイント別の細粒度制限（Redis バックエンド）
- **監査ログミドルウェア**: 全 HTTP リクエストの自動記録・SHA-256 ハッシュチェーン
- **CORS ミドルウェア**: 環境別オリジン制御
- **TrustedHost ミドルウェア**: ホスト名インジェクション防止
- セキュリティミドルウェアテスト 22件（カバレッジ 98%）

### Changed
- `main.py`: ミドルウェアチェーン順序の最適化（外→内: Audit → RateLimit → SecurityHeaders → CORS → TrustedHost）

---

## [0.13.0] - 2026-03-23

### Added
- **監査ログ API** (`/audit-logs`): 検索・フィルタリング・CSV エクスポート
- 監査ログの SHA-256 ハッシュチェーン整合性検証
- 28種類のイベントタイプ対応（認証・ユーザー管理・ロール・申請・システム）
- SIEM 連携用イベント構造化

---

## [0.12.0] - 2026-03-22

### Added
- **ワークフロー API** (`/workflows`): プロビジョニング・デプロビジョニングフロー
- **Celery タスク基盤**: AD / EntraID / HENGEONE への非同期プロビジョニング
- Redis ブローカー経由のタスクキュー管理
- Flower によるタスク監視インターフェース

---

## [0.11.0] - 2026-03-21

### Added
- **アクセス申請 API** (`/access-requests`): 申請・承認・却下フロー
- 申請ステータス遷移管理（pending → approved/rejected → expired）
- 特権アクセス申請の多段階承認フロー
- 申請期限（TTL）管理

---

## [0.10.0] - 2026-03-20

### Added
- **HENGEONE 連携**: REST API 経由でのアカウント管理・MFA 設定
- **Active Directory 連携**: ldap3 クライアントによる LDAP/LDAPS 操作
- **EntraID 連携**: Microsoft Graph API / Delta Query による差分同期
- **Webhook 設計**: HMAC-SHA256 シグネチャ検証・冪等性保証

---

## [0.9.0] - 2026-03-19

### Added
- **ロール管理 API** (`/roles`): RBAC ロール定義・ユーザーへの割り当て・取消
- ロール階層管理（system / business / external）
- 特権ロール (`is_privileged`) の承認フロー連携
- ロール割り当て有効期限（`expires_at`）管理

---

## [0.8.0] - 2026-03-18

### Added
- **ユーザー管理 API** (`/users`): CRUD 操作・検索・フィルタリング
- ページネーション対応（`page` + `per_page`）
- アカウント状態管理（active / disabled / locked）
- リスクスコア計算・更新機能

---

## [0.7.0] - 2026-03-17

### Added
- **JWT 認証基盤**: アクセストークン（15分）+ リフレッシュトークン（7日）
- Redis によるトークンブラックリスト（ログアウト・失効管理）
- `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh` エンドポイント
- JWE（暗号化トークン）オプション対応

### Security
- JWT `jti`（JWT ID）によるリプレイアタック防止
- トークンタイプ (`access` / `refresh`) 検証によるトークン流用防止

---

## [0.6.0] - 2026-03-16

### Added
- **RBAC エンジン**: パーミッションマトリクス・ロールチェック
- `GlobalAdmin`, `TenantAdmin`, `Operator`, `Auditor`, `ReadOnly` ロール定義
- FastAPI `Depends` による権限デコレータ

---

## [0.5.0] - 2026-03-15

### Added
- **PostgreSQL データモデル**: users / roles / user_roles / access_requests / audit_logs / departments テーブル
- **Alembic マイグレーション基盤**: バージョン管理・CI 自動実行
- **SQLAlchemy 非同期 ORM**: `AsyncSession` によるパフォーマンス最適化
- PgBouncer 接続プーリング設定

---

## [0.4.0] - 2026-03-14

### Added
- **FastAPI アプリケーション基盤**: 非同期 ASGI サーバー（uvicorn）
- RFC 7807 Problem Details 形式のエラーハンドリング
- OpenAPI / Swagger UI 自動生成（`/docs`, `/redoc`）
- Pydantic v2 によるリクエスト/レスポンスバリデーション

---

## [0.3.0] - 2026-03-13

### Added
- **Next.js 14 フロントエンド**: App Router / TypeScript
- SWR によるデータフェッチング・stale-while-revalidate キャッシュ戦略
- sessionStorage JWT トークン管理
- Recharts ダッシュボードコンポーネント

---

## [0.2.0] - 2026-03-12

### Added
- **Docker Compose 開発環境**: backend / frontend / db / redis / worker / flower
- 環境変数管理（`.env` / Azure Key Vault）
- GitHub Actions CI パイプライン基盤

---

## [0.1.0] - 2026-03-10

### Added
- プロジェクト初期化
- リポジトリ構造設計
- README.md（システム概要・技術スタック）
- `CONTRIBUTING.md`, `LICENSE`
- Issue テンプレート・PR テンプレート
