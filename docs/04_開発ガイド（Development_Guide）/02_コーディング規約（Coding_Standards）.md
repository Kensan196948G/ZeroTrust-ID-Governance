# コーディング規約（Coding Standards Guide）

| 項目 | 内容 |
|------|------|
| 文書番号 | DEV-STD-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-24 |
| 最終更新 | 2026-03-24 |
| 対象プロジェクト | ZeroTrust-ID-Governance |
| 担当 | 開発チーム |
| ステータス | 有効 |

---

## 目次

1. [Python コーディング規約](#1-python-コーディング規約)
2. [TypeScript コーディング規約](#2-typescript-コーディング規約)
3. [ファイル・ディレクトリ命名規則](#3-ファイルディレクトリ命名規則)
4. [コミットメッセージ規約](#4-コミットメッセージ規約)
5. [ブランチ命名規則](#5-ブランチ命名規則)
6. [PR 作成規約](#6-pr-作成規約)
7. [コードレビューチェックリスト](#7-コードレビューチェックリスト)

---

## 1. Python コーディング規約

### 1.1 フォーマッタ・リンター設定

本プロジェクトでは以下のツールを使用します。

| ツール | 用途 | 設定ファイル |
|--------|------|------------|
| `ruff` | フォーマット・Lint（isort/flake8 代替） | `pyproject.toml` |
| `mypy` | 静的型チェック | `pyproject.toml` |
| `black` | コードフォーマット（ruff と併用可） | `pyproject.toml` |
| `bandit` | セキュリティ Lint | `pyproject.toml` |

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "S",   # bandit
    "N",   # pep8-naming
]
ignore = ["S101"]  # assert 文を許可（テストコード用）

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
disallow_untyped_defs = true
disallow_any_generics = false
```

### 1.2 型ヒント（Type Hints）必須ルール

**すべての関数・メソッドに型ヒントを付与すること。**

```python
# NG: 型ヒントなし
def get_user(user_id):
    return db.get(user_id)

# OK: 型ヒントあり
from uuid import UUID
from app.models.user import User

async def get_user(user_id: UUID) -> User | None:
    return await db.get(User, user_id)
```

```python
# 複合型の例
from typing import Sequence
from collections.abc import AsyncGenerator

async def get_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = None,
) -> Sequence[User]:
    ...

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    ...
```

### 1.3 Docstring 規約

**すべての公開関数・クラス・モジュールに docstring を記述すること。**
形式は **Google スタイル** を採用します。

```python
def authenticate_user(email: str, password: str) -> User | None:
    """メールアドレスとパスワードでユーザーを認証する。

    Args:
        email: ユーザーのメールアドレス。
        password: 平文パスワード（ハッシュ検証前）。

    Returns:
        認証成功時は User オブジェクト、失敗時は None。

    Raises:
        ValueError: email の形式が不正な場合。
        DatabaseError: DB 接続エラーが発生した場合。

    Example:
        >>> user = authenticate_user("user@example.com", "password123")
        >>> assert user is not None
    """
    ...
```

### 1.4 FastAPI エンドポイント規約

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserCreate, UserResponse
from app.services.user import UserService
from app.core.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新規ユーザー作成",
    description="新しいユーザーを作成し、作成されたユーザー情報を返す。",
)
async def create_user(
    user_data: UserCreate,
    service: UserService = Depends(),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """新規ユーザーを作成するエンドポイント。"""
    return await service.create(user_data)
```

### 1.5 例外処理規約

```python
# NG: 素の Exception をキャッチ
try:
    result = await service.process()
except Exception:
    pass

# OK: 具体的な例外をキャッチし、適切にログ出力
import logging
from app.core.exceptions import DatabaseError, NotFoundError

logger = logging.getLogger(__name__)

try:
    result = await service.process()
except NotFoundError as e:
    logger.warning("Resource not found: %s", e)
    raise HTTPException(status_code=404, detail=str(e)) from e
except DatabaseError as e:
    logger.error("Database error occurred: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error") from e
```

### 1.6 非同期処理規約

```python
# NG: 同期関数内でブロッキング処理
def get_user_sync(user_id: UUID) -> User:
    time.sleep(1)  # ブロッキング

# OK: 非同期関数を使用
async def get_user(user_id: UUID) -> User | None:
    async with AsyncSession() as session:
        return await session.get(User, user_id)

# NG: asyncio.run() を非同期コンテキストで使用しない
async def bad_example():
    result = asyncio.run(some_coroutine())  # エラーになる

# OK: await を使用
async def good_example():
    result = await some_coroutine()
```

### 1.7 lint・型チェックの実行

```bash
# Lint チェック
ruff check backend/

# フォーマット適用
ruff format backend/

# 型チェック
mypy backend/

# セキュリティチェック
bandit -r backend/app/

# 全チェックを一括実行
make lint
```

---

## 2. TypeScript コーディング規約

### 2.1 ESLint・tsc 設定

| ツール | 用途 | 設定ファイル |
|--------|------|------------|
| `ESLint` | Lint チェック | `.eslintrc.json` |
| `TypeScript` (strict) | 型チェック | `tsconfig.json` |
| `Prettier` | コードフォーマット | `.prettierrc` |

```json
// tsconfig.json（主要設定抜粋）
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true
  }
}
```

```json
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "plugin:@typescript-eslint/recommended-type-checked",
    "plugin:@typescript-eslint/stylistic-type-checked"
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/consistent-type-imports": "error",
    "prefer-const": "error"
  }
}
```

### 2.2 React コンポーネント規約

**関数コンポーネントを使用し、クラスコンポーネントは使用しない。**

```tsx
// NG: any 型の使用、Props 型定義なし
const UserCard = ({ user }: any) => {
  return <div>{user.name}</div>;
};

// OK: 明示的な Props 型定義、適切な型ヒント
import type { FC } from "react";

type UserCardProps = {
  userId: string;
  displayName: string;
  email: string;
  role: "admin" | "manager" | "operator" | "viewer";
  isActive?: boolean;
};

const UserCard: FC<UserCardProps> = ({
  userId,
  displayName,
  email,
  role,
  isActive = true,
}) => {
  return (
    <div className="user-card" data-testid={`user-card-${userId}`}>
      <h3>{displayName}</h3>
      <p>{email}</p>
      <span className={`badge badge-${role}`}>{role}</span>
    </div>
  );
};

export default UserCard;
```

### 2.3 カスタムフック規約

```tsx
// hooks/useUser.ts
import { useState, useEffect } from "react";
import type { User } from "@/types/user";
import { fetchUser } from "@/lib/api/user";

type UseUserReturn = {
  user: User | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
};

export function useUser(userId: string): UseUserReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = async (): Promise<void> => {
    setIsLoading(true);
    try {
      const data = await fetchUser(userId);
      setUser(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Unknown error"));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refetch();
  }, [userId]);

  return { user, isLoading, error, refetch };
}
```

### 2.4 API クライアント規約

```typescript
// lib/api/client.ts
import type { ApiResponse } from "@/types/api";

// NG: fetch をそのまま使用、エラーハンドリングなし
const data = await fetch("/api/users").then((r) => r.json());

// OK: 共通クライアント経由、型安全
async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json() as Promise<ApiResponse<T>>;
}
```

### 2.5 lint・型チェックの実行

```bash
# ESLint チェック
npm run lint

# ESLint 自動修正
npm run lint -- --fix

# 型チェック
npm run type-check
# または
npx tsc --noEmit

# フォーマット適用
npx prettier --write "src/**/*.{ts,tsx}"
```

---

## 3. ファイル・ディレクトリ命名規則

### 3.1 バックエンド（Python）

| 対象 | 規則 | 例 |
|------|------|-----|
| ファイル名 | `snake_case` | `user_service.py` |
| ディレクトリ名 | `snake_case` | `api/v1/endpoints/` |
| クラス名 | `PascalCase` | `UserService`, `TokenValidator` |
| 関数・メソッド名 | `snake_case` | `get_user_by_email()` |
| 変数名 | `snake_case` | `access_token`, `user_id` |
| 定数名 | `UPPER_SNAKE_CASE` | `JWT_ALGORITHM`, `MAX_RETRY_COUNT` |
| 型エイリアス | `PascalCase` | `UserList = list[User]` |
| Enum | `PascalCase` / 値は `UPPER_SNAKE_CASE` | `class UserRole(str, Enum): ADMIN = "admin"` |

### 3.2 フロントエンド（TypeScript/Next.js）

| 対象 | 規則 | 例 |
|------|------|-----|
| コンポーネントファイル | `PascalCase` | `UserCard.tsx`, `AuthGuard.tsx` |
| ページファイル | `kebab-case`（Next.js App Router） | `page.tsx`, `layout.tsx` |
| フックファイル | `camelCase` with `use` prefix | `useUser.ts`, `useAuth.ts` |
| ユーティリティファイル | `camelCase` | `formatDate.ts`, `apiClient.ts` |
| 型定義ファイル | `camelCase` | `user.ts`, `apiResponse.ts` |
| ディレクトリ名 | `kebab-case` | `user-management/`, `auth/` |
| コンポーネント名 | `PascalCase` | `UserCard`, `LoginForm` |
| 変数・関数名 | `camelCase` | `userId`, `getUser()` |
| 定数 | `UPPER_SNAKE_CASE` | `API_BASE_URL`, `MAX_RETRY` |
| CSS クラス名 | `kebab-case` | `user-card`, `btn-primary` |

### 3.3 ディレクトリ構造規約

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/    # APIルータ（snake_case）
│   ├── core/                 # 設定・依存性注入
│   ├── models/               # SQLAlchemy モデル
│   ├── schemas/              # Pydantic スキーマ
│   ├── services/             # ビジネスロジック
│   ├── repositories/         # データアクセス層
│   └── utils/                # ユーティリティ
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── alembic/
    └── versions/

frontend/
├── src/
│   ├── app/                  # Next.js App Router
│   │   └── (auth)/           # ルートグループ
│   ├── components/           # 共有コンポーネント（PascalCase）
│   │   ├── ui/               # 基本 UI コンポーネント
│   │   └── features/         # 機能コンポーネント
│   ├── hooks/                # カスタムフック
│   ├── lib/                  # ユーティリティ・API クライアント
│   ├── types/                # TypeScript 型定義
│   └── styles/               # グローバルスタイル
└── tests/
    ├── unit/
    └── e2e/
```

---

## 4. コミットメッセージ規約

### 4.1 Conventional Commits 形式

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### 4.2 Type 一覧

| Type | 説明 | 例 |
|------|------|-----|
| `feat` | 新機能の追加 | `feat(auth): JWT リフレッシュトークン機能を追加` |
| `fix` | バグ修正 | `fix(user): メールアドレス重複チェックの不具合を修正` |
| `docs` | ドキュメントのみの変更 | `docs(api): ユーザー API の説明を更新` |
| `style` | コードの意味に影響しない変更（空白、フォーマット等） | `style: ruff フォーマット適用` |
| `refactor` | バグ修正でも機能追加でもないコード変更 | `refactor(service): UserService をリポジトリパターンに移行` |
| `perf` | パフォーマンス改善 | `perf(db): N+1 クエリを解消` |
| `test` | テストの追加・修正 | `test(auth): ログイン API の統合テストを追加` |
| `chore` | ビルドプロセス・補助ツールの変更 | `chore: Docker Compose の Python バージョンを 3.11 に更新` |
| `ci` | CI 設定の変更 | `ci: GitHub Actions に mypy チェックを追加` |
| `revert` | 直前のコミットを取り消す | `revert: feat(auth): リフレッシュトークン機能を追加` |
| `security` | セキュリティ修正 | `security(auth): トークン漏洩の脆弱性を修正` |

### 4.3 Scope 一覧（例）

| Scope | 対象範囲 |
|-------|---------|
| `auth` | 認証・認可 |
| `user` | ユーザー管理 |
| `role` | ロール・権限 |
| `api` | API エンドポイント |
| `db` | データベース関連 |
| `ui` | フロントエンド UI |
| `infra` | インフラ・Docker |
| `ci` | CI/CD |
| `deps` | 依存関係 |

### 4.4 コミットメッセージ例

```
feat(auth): TOTP ベースの多要素認証を追加

Google Authenticator 互換の TOTP 実装を追加。
ユーザーごとに MFA を有効/無効化できる設定も追加した。

- pyotp ライブラリを使用
- QR コード生成エンドポイントを追加（/api/v1/auth/mfa/setup）
- MFA 検証エンドポイントを追加（/api/v1/auth/mfa/verify）

Closes #42
```

```
fix(rbac): 権限チェックで OR 条件が正常に評価されない問題を修正

複数のパーミッションを OR 条件でチェックする際に、
最初の条件のみ評価される不具合があったため修正。

Fixes #87
```

### 4.5 コミットメッセージのルール

- **subject は命令形・現在形で記述**（「追加した」ではなく「追加する」または「追加」）
- **subject は 72 文字以内**
- **subject の末尾にピリオドをつけない**
- **body は subject と空行で区切る**
- **body で「なぜ」変更したかを説明する**
- **Issue 番号は footer に記載**（`Closes #123`, `Fixes #456`）

---

## 5. ブランチ命名規則

### 5.1 ブランチ命名パターン

```
<type>/phase-<XX>-<description>
```

| パターン | 説明 | 例 |
|---------|------|-----|
| `feature/phase-<XX>-<description>` | 新機能開発 | `feature/phase-03-jwt-authentication` |
| `fix/phase-<XX>-<description>` | バグ修正 | `fix/phase-03-token-expiry-bug` |
| `hotfix/<description>` | 緊急修正（本番障害） | `hotfix/critical-auth-bypass` |
| `refactor/phase-<XX>-<description>` | リファクタリング | `refactor/phase-05-user-service` |
| `docs/<description>` | ドキュメント更新 | `docs/update-api-specification` |
| `ci/<description>` | CI/CD 設定変更 | `ci/add-security-scan` |
| `chore/<description>` | その他メンテナンス | `chore/upgrade-fastapi-0.110` |

### 5.2 ブランチ運用ルール

| ルール | 説明 |
|--------|------|
| `main` ブランチへの直接 push 禁止 | 必ず PR 経由でマージ |
| `develop` ブランチへの直接 push 禁止 | 必ず PR 経由でマージ |
| 作業ブランチは `develop` から派生 | `git checkout -b feature/xxx develop` |
| ブランチ名に日本語を使用しない | ASCII 文字のみ使用 |
| `XX` はフェーズ番号（2桁） | Phase 3 → `03`、Phase 12 → `12` |

```bash
# ブランチ作成例
git checkout develop
git pull origin develop
git checkout -b feature/phase-03-jwt-authentication

# 作業完了後
git push origin feature/phase-03-jwt-authentication
# → GitHub で PR を作成
```

---

## 6. PR 作成規約

### 6.1 PR タイトル規約

コミットメッセージと同様に Conventional Commits 形式を使用します。

```
<type>(<scope>): <subject>
```

例:
- `feat(auth): JWT 認証機能の実装（Phase 3）`
- `fix(user): メールアドレス変更時のバリデーション修正`

### 6.2 PR 説明テンプレート

```markdown
## 概要
<!-- この PR で何をしたかを簡潔に説明 -->

## 変更内容
<!-- 変更の詳細をリストアップ -->
- [ ] 変更点1
- [ ] 変更点2

## 関連 Issue
<!-- Closes #<issue番号> -->
Closes #

## テスト確認
- [ ] ユニットテスト追加・実行済み
- [ ] 統合テスト実行済み
- [ ] 手動動作確認済み
- [ ] CI 全通過確認済み

## レビュアーへの注意事項
<!-- レビュアーが特に注目すべき点があれば記載 -->

## スクリーンショット（UI 変更がある場合）
<!-- 変更前後のスクリーンショットを添付 -->
```

### 6.3 PR 作成時のルール

| ルール | 詳細 |
|--------|------|
| CI 通過確認 | PR 作成前に全 CI チェックが通過していること |
| コンフリクト解消 | develop ブランチとのコンフリクトを事前に解消 |
| セルフレビュー | PR 作成前に自分でコードを確認 |
| 適切なラベル付与 | `feature` / `bug` / `documentation` 等のラベルを設定 |
| レビュアー指定 | 少なくとも1名をレビュアーとして指定 |
| Draft PR 活用 | 作業中は Draft PR として作成し、完成後に Ready に変更 |
| 差分の大きさ | 1 PR あたり変更行数は 400 行以内を目安とする |

---

## 7. コードレビューチェックリスト

### 7.1 レビュアー向けチェックリスト

#### セキュリティ

- [ ] 認証・認可が適切に実装されているか
- [ ] SQL インジェクション対策がされているか（ORM 使用、パラメータバインド）
- [ ] 機密情報（パスワード、トークン）がログに出力されていないか
- [ ] 入力値バリデーションが適切か（Pydantic / Zod）
- [ ] CORS 設定が適切か
- [ ] JWT トークンの有効期限・検証が正しいか

#### コード品質

- [ ] 型ヒント（Python）または型定義（TypeScript）が適切か
- [ ] docstring / JSDoc が主要な関数に記述されているか
- [ ] 重複コードがなく、DRY 原則に従っているか
- [ ] 関数・メソッドが単一責任の原則を守っているか
- [ ] マジックナンバーや文字列が定数化されているか
- [ ] エラーハンドリングが適切か
- [ ] ログが適切なレベルで出力されているか

#### テスト

- [ ] ユニットテストが追加されているか
- [ ] ハッピーパスと異常系のテストが含まれているか
- [ ] テストカバレッジが規定値（80%以上）を満たしているか
- [ ] モック・スタブが適切に使用されているか

#### パフォーマンス

- [ ] N+1 クエリが発生していないか
- [ ] 不要な DB クエリが実行されていないか
- [ ] キャッシュが適切に活用されているか
- [ ] 大量データ処理でページネーションが実装されているか

#### 可読性・保守性

- [ ] 変数名・関数名がその意図を明確に表しているか
- [ ] 複雑なロジックにコメントが付いているか
- [ ] 命名規則に従っているか
- [ ] 不要なコメントアウトコードが残っていないか

### 7.2 レビュー返答の優先度表記

| プレフィックス | 意味 | 対応 |
|--------------|------|------|
| `[Blocker]` | マージ前に必ず修正が必要 | 必須対応 |
| `[Must]` | 修正すべき問題 | 原則対応 |
| `[Should]` | できれば修正してほしい | 推奨対応 |
| `[Nit]` | 細かい指摘（好み） | 任意対応 |
| `[Question]` | 質問・確認 | 返答必須 |
| `[FYI]` | 情報共有・参考まで | 対応不要 |

### 7.3 レビュー完了基準

| 基準 | 説明 |
|------|------|
| Approve 数 | レビュアー1名以上の Approve が必要 |
| CI 状態 | 全 CI チェックが `✅ passed` であること |
| コンフリクト | `develop` との衝突がないこと |
| Blocker 解消 | `[Blocker]` コメントが全て解消されていること |
| Draft 解除 | Draft 状態が解除されていること |

---

*文書番号: DEV-STD-001 | バージョン: 1.0.0 | 最終更新: 2026-03-24*
