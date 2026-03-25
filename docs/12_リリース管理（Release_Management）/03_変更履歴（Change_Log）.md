# 変更履歴（Change Log）

| 項目 | 内容 |
|------|------|
| 文書番号 | REL-CL-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 最終更新日 | 2026-03-25 |
| 作成者 | DevOps Engineer |
| フォーマット | Keep a Changelog 1.0.0 準拠 |
| ステータス | 承認済み |

---

> すべての注目すべき変更をこのファイルに記録する。
>
> フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づき、
> [セマンティックバージョニング](https://semver.org/lang/ja/) に従う。

---

## [Unreleased]

### 追加予定 (Planned)
- Phase 16: Microsoft Entra ID 完全統合（SAML / OIDC）
- Phase 17: Active Directory リアルタイム同期強化
- Phase 18: HENGEONE プロキシ統合
- Phase 19: BI ダッシュボード・コンプライアンスレポート

---

## [0.15.0] — 2026-03-25 (Phase 15: E2E テスト実装)

### 追加 (Added)
- **Playwright E2E テストスイート**を実装
  - ログイン / ログアウト / MFA フローの E2E テスト
  - ユーザー管理（作成・更新・削除・検索）の E2E テスト
  - ロール管理（付与・解除・権限確認）の E2E テスト
  - 監査ログ閲覧・フィルタ・エクスポートの E2E テスト
- 認証異常系の E2E テスト（パスワード誤り / アカウントロック / MFA失敗）
- セキュリティシナリオの E2E テスト（CSRF / XSS 防御確認）
- CI ワークフローに Playwright テストジョブを追加（`e2e.yml`）
- ステージング環境向け Playwright 設定（`playwright.staging.config.ts`）

### 変更 (Changed)
- GitHub Actions の CI パイプラインを E2E テスト対応に拡張
- テスト並列実行の最適化（シャーディング対応）
- STABLE 判定基準に E2E テスト通過を追加

### 修正 (Fixed)
- フロントエンドのトークンリフレッシュ処理でのレース条件を修正
- 監査ログ画面のページネーションバグを修正
- ロール管理画面でのチェックボックス状態同期バグを修正

### セキュリティ (Security)
- Playwright による XSS 防御の自動検証テストを追加
- CSRF トークン検証の自動テストを追加

---

## [0.14.0] — 2026-02-03 (Phase 14: セキュリティミドルウェア強化)

### 追加 (Added)
- **WAF ルール**をアプリケーションレベルで実装
- **SQL インジェクション防御**の強化（ORM バリデーション層追加）
- **XSS フィルタ**（Content-Security-Policy ヘッダー強化）
- **CSRF 保護**（Double Submit Cookie パターン実装）
- セキュリティヘッダー自動設定ミドルウェア
  - `Strict-Transport-Security`
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
- OWASP ZAP 自動スキャンの CI 統合（`security.yml`）
- Semgrep SAST スキャンの CI 統合

### 変更 (Changed)
- 入力バリデーションを Pydantic v2 のモデルバリデーターに統一
- CORS 設定をより厳格なホワイトリスト方式に変更
- レート制限の閾値を調整（認証エンドポイント: 10req/min → 5req/min）

### 修正 (Fixed)
- ヘッダーインジェクション脆弱性を修正
- オープンリダイレクト脆弱性を修正

### セキュリティ (Security)
- Trivy スキャンで検出された中程度の脆弱性 3件を修正
- 依存ライブラリのセキュリティアップデート（cryptography, Pillow）

---

## [0.13.0] — 2026-01-27 (Phase 13: テストカバレッジ向上)

### 追加 (Added)
- **テストカバレッジ 95% 達成**（Phase 12 時点の 82% から向上）
- 認証エンジンの追加単体テスト（エッジケース対応）
  - 期限切れトークンの処理
  - 無効な署名トークンの処理
  - 同時ログインセッションの制限
- RBAC エンジンの境界値テスト
- 監査ログミドルウェアの統合テスト拡充
- パラメータ化テスト（`@pytest.mark.parametrize`）の活用
- `freezegun` を使用した時刻依存テストの実装
- Codecov との GitHub Actions 連携設定

### 変更 (Changed)
- テストディレクトリ構成をリファクタリング（`unit/` / `integration/` / `e2e/` 分離）
- テストフィクスチャを共通化（`conftest.py` の整備）
- モック戦略の統一（外部 API は常にモック）

### 修正 (Fixed)
- 一部テストでのデータベース状態汚染バグを修正（トランザクションロールバック対応）

---

## [0.12.0] — 2026-01-20 (Phase 12: フロントエンド管理画面)

### 追加 (Added)
- **ユーザー管理画面**（一覧・検索・作成・編集・削除）
- **ロール管理画面**（ロール一覧・権限付与・解除）
- **監査ログ閲覧画面**（一覧・フィルタ・エクスポート）
- **ダッシュボード画面**（統計情報・最近のログイン・アクティビティ）
- **アクセス申請管理画面**（申請一覧・承認・却下）
- ダークモード対応
- レスポンシブデザイン対応（モバイル / タブレット）
- データテーブルコンポーネント（ソート / フィルタ / ページネーション）

### 変更 (Changed)
- フロントエンドの状態管理を Zustand に統一
- API クライアントのエラーハンドリングを強化
- ルーティング設定を Next.js App Router に移行

### 修正 (Fixed)
- 管理画面での権限チェックが不完全だった問題を修正
- セッションタイムアウト時のリダイレクト処理バグを修正

---

## [0.11.0] — 2026-01-06 (Phase 11: フロントエンド認証 UI)

### 追加 (Added)
- **ログイン画面**（メール + パスワード認証）
- **MFA 入力画面**（TOTP / SMS 対応）
- **パスワードリセット画面**（メール送信 / リセット完了）
- **初回ログイン画面**（パスワード変更強制）
- セッション管理 UI（有効期限表示 / 延長ダイアログ）
- ログイン失敗時のエラーメッセージ（日本語対応）
- パスワード強度インジケーター
- アクセシビリティ対応（WAI-ARIA）

### 変更 (Changed)
- 認証状態管理を NextAuth.js から独自実装に移行（JWT 管理の柔軟性向上）
- フォームバリデーションを React Hook Form + Zod に統一

### セキュリティ (Security)
- パスワードフィールドの autocomplete 属性を適切に設定
- フォームの CSRF 対策を実装

---

## [0.10.0] — 2025-12-23 (Phase 10: フロントエンド基盤)

### 追加 (Added)
- **Next.js 14 フロントエンド**プロジェクト初期セットアップ
  - App Router 構成
  - TypeScript 設定
  - Tailwind CSS + shadcn/ui コンポーネントライブラリ
- **認証プロバイダー**（AuthContext / useAuth フック）
- **API クライアント**（axios ベース / インターセプター設定）
- **共通レイアウト**（Header / Sidebar / Footer）
- フロントエンド向け CI ワークフロー（`frontend-ci.yml`）
  - ESLint / TypeScript チェック
  - Jest 単体テスト
  - Next.js ビルド確認
- Docker 構成にフロントエンドサービスを追加

### 変更 (Changed)
- `docker-compose.yml` にフロントエンドコンテナを追加

---

## [0.9.0] — 2025-12-09 (Phase 9: エンジンカバレッジ向上)

### 追加 (Added)
- 認証エンジンの網羅的テスト（カバレッジ 90% 達成）
- RBAC エンジンのエッジケーステスト
- パフォーマンステスト（k6 による負荷テストスクリプト）
- テストレポートの自動生成・GitHub Actions アーティファクト保存

### 変更 (Changed)
- 認証エンジンのリファクタリング（依存関係の注入を強化）
- エラーメッセージの標準化

### 修正 (Fixed)
- 同時リクエスト時のトークン検証でのレース条件を修正
- ロールキャッシュの無効化タイミングバグを修正

---

## [0.8.0] — 2025-12-02 (Phase 8: RBAC 細分化)

### 追加 (Added)
- **RBAC 細分化**（リソース × アクション の組み合わせで権限定義）
  - `users:read` / `users:write` / `users:delete`
  - `roles:read` / `roles:write` / `roles:delete`
  - `audit_logs:read` / `audit_logs:export`
  - `access_requests:read` / `access_requests:approve`
- **権限継承モデル**（ロール階層による権限の継承）
- **リソースレベルアクセス制御**（行レベルセキュリティ）
- 権限マトリクス管理 API（`GET /api/v1/rbac/permissions-matrix`）

### 変更 (Changed)
- 既存のロールを新しい細粒度権限体系に移行
- `check_permission` デコレータを新権限体系対応に更新

### セキュリティ (Security)
- 最小権限原則を強化（管理者権限をさらに細分化）

---

## [0.7.0] — 2025-11-25 (Phase 7: JWT 失効管理)

### 追加 (Added)
- **JWT トークンブラックリスト**（Redis を使用したトークン失効管理）
- **リフレッシュトークン管理**（長期セッション対応）
- **セッション管理 API**
  - `GET /api/v1/auth/sessions` — アクティブセッション一覧
  - `DELETE /api/v1/auth/sessions/{session_id}` — セッション強制終了
  - `DELETE /api/v1/auth/sessions` — 全セッション強制終了
- 同時ログイン数の制限機能（最大 5セッション）
- トークン有効期限の設定（アクセストークン: 15分 / リフレッシュトークン: 7日）

### 変更 (Changed)
- ログアウト処理がトークンをブラックリストに追加するよう変更
- Redis キャッシュ設定の最適化

### セキュリティ (Security)
- パスワード変更時に全セッションを無効化する機能を追加
- 不審なログイン（新規 IP / 深夜帯）の検知フラグ追加

---

## [0.6.0] — 2025-11-18 (Phase 6: 監査ログミドルウェア)

### 追加 (Added)
- **監査ログミドルウェア**（FastAPI ミドルウェアで全リクエストを自動記録）
  - リクエスト / レスポンス情報の記録
  - ユーザー ID / IP アドレス / User-Agent の記録
  - 処理時間の記録
- 監査ログ API
  - `GET /api/v1/audit-logs` — ログ一覧（フィルタ・ページネーション対応）
  - `GET /api/v1/audit-logs/{id}` — ログ詳細
  - `GET /api/v1/audit-logs/export` — CSV エクスポート
- ログローテーション設定
- 個人情報マスキング処理（パスワード / トークンの自動マスク）

### 変更 (Changed)
- ログフォーマットを JSON 構造化ログに統一
- 既存のアプリケーションログを構造化ログに移行

### セキュリティ (Security)
- 監査ログへの書き込み専用アクセス制御を実装（読み取りは権限者のみ）

---

## [0.5.0] — 2025-11-11 (Phase 5: セキュリティ強化)

### 追加 (Added)
- **レート制限**（`slowapi` による IP ベースレート制限）
  - ログインエンドポイント: 5req/min
  - API 全般: 100req/min
- **CORS 設定**（許可オリジンのホワイトリスト管理）
- **セキュリティヘッダー**の自動付与
- **入力バリデーション強化**（Pydantic v2 バリデーター）
- **アカウントロック**機能（5回失敗でロック / 30分後自動解除）
- Bandit / safety の CI 統合
- Trivy コンテナスキャンの CI 統合

### 変更 (Changed)
- パスワードハッシュアルゴリズムを bcrypt (work factor=12) に統一
- ログインエラーメッセージを汎用化（ユーザー名/パスワード不明確化）

### セキュリティ (Security)
- タイミング攻撃対策（`hmac.compare_digest` によるハッシュ比較）
- セッションフィクセーション攻撃対策

---

## [0.4.0] — 2025-11-04 (Phase 4: ユーザー管理 API)

### 追加 (Added)
- ユーザー CRUD API
  - `GET /api/v1/users` — ユーザー一覧
  - `POST /api/v1/users` — ユーザー作成
  - `GET /api/v1/users/{id}` — ユーザー詳細
  - `PUT /api/v1/users/{id}` — ユーザー更新
  - `DELETE /api/v1/users/{id}` — ユーザー削除
- プロファイル管理 API（`GET/PUT /api/v1/users/me`）
- パスワードポリシー実装（長さ / 複雑性 / 有効期限）
- パスワード変更 API（`PUT /api/v1/users/me/password`）
- ユーザー検索 API（`GET /api/v1/users?q={query}`）

### 変更 (Changed)
- ユーザーモデルに `is_active` / `last_login_at` / `password_changed_at` フィールドを追加

---

## [0.3.0] — 2025-10-28 (Phase 3: 認証 API 実装)

### 追加 (Added)
- **JWT 認証システム**（RS256 署名）
- **OAuth2 フロー**（Password Grant / Client Credentials）
- 認証 API エンドポイント
  - `POST /api/v1/auth/login` — ログイン
  - `POST /api/v1/auth/logout` — ログアウト
  - `POST /api/v1/auth/refresh` — トークンリフレッシュ
  - `GET /api/v1/auth/me` — 認証済みユーザー情報
- `require_auth` / `require_role` デコレータ
- JWT 鍵ペア管理（RSA 2048bit）

---

## [0.2.0] — 2025-10-14 (Phase 2: DB モデル実装)

### 追加 (Added)
- **SQLAlchemy ORM モデル**
  - `users` — ユーザー情報
  - `roles` — ロール定義
  - `permissions` — 権限定義
  - `user_roles` — ユーザー × ロール 関連
  - `role_permissions` — ロール × 権限 関連
  - `audit_logs` — 監査ログ
  - `access_requests` — アクセス申請
- **Alembic マイグレーション**基盤
- **PostgreSQL 接続設定**（接続プール / SSL 対応）
- **Redis 接続設定**
- モデルのユニットテスト

---

## [0.1.0] — 2025-10-07 (Phase 1: プロジェクト初期設定)

### 追加 (Added)
- **プロジェクトリポジトリ初期設定**
- **Docker Compose** ローカル開発環境（backend / frontend / postgres / redis）
- **GitHub Actions** CI/CD 基盤
  - `ci.yml` — Lint / テスト / カバレッジ
  - `security.yml` — セキュリティスキャン
- **pre-commit フック**（black / isort / flake8）
- **pyproject.toml**（Poetry 依存関係管理）
- FastAPI アプリケーション基本構成
- プロジェクト README / ドキュメント基盤
- `CLAUDE.md` — ClaudeOS v4 エージェント設定

---

[Unreleased]: https://github.com/org/zerotrust-idg/compare/v0.15.0...HEAD
[0.15.0]: https://github.com/org/zerotrust-idg/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/org/zerotrust-idg/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/org/zerotrust-idg/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/org/zerotrust-idg/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/org/zerotrust-idg/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/org/zerotrust-idg/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/org/zerotrust-idg/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/org/zerotrust-idg/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/org/zerotrust-idg/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/org/zerotrust-idg/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/org/zerotrust-idg/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/org/zerotrust-idg/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/org/zerotrust-idg/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/org/zerotrust-idg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/org/zerotrust-idg/releases/tag/v0.1.0
