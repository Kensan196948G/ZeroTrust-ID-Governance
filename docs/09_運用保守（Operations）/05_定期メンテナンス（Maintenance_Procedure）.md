# 定期メンテナンス手順書

| 項目 | 内容 |
|------|------|
| 文書番号 | OPS-MAINT-001 |
| バージョン | 1.0.0 |
| 作成日 | 2026-03-25 |
| 作成者 | インフラチーム |
| 承認者 | CTO |
| 対象システム | ZeroTrust-ID-Governance（Azure AKS / Prometheus / Grafana / Azure Monitor / PgBouncer / Celery） |

---

## 目次

1. [概要](#概要)
2. [メンテナンスウィンドウ設定](#メンテナンスウィンドウ設定)
3. [OS・ミドルウェアパッチ適用手順](#osミドルウェアパッチ適用手順)
4. [Kubernetes ノードメンテナンス](#kubernetes-ノードメンテナンス)
5. [DB バキューム・ANALYZE 実行](#db-バキュームanalyze-実行)
6. [SSL証明書更新手順](#ssl証明書更新手順)
7. [シークレット・APIキーのローテーション](#シークレットapiキーのローテーション)
8. [メンテナンス前後チェックリスト](#メンテナンス前後チェックリスト)

---

## 概要

本書は ZeroTrust-ID-Governance システムの定期メンテナンス手順を定義します。
計画的なメンテナンスを実施することで、セキュリティリスクの低減・システムパフォーマンスの維持・長期安定稼働を実現します。

### メンテナンス分類

| 種別 | 頻度 | 目的 |
|------|------|------|
| ノードパッチ | 月次 | OS / セキュリティパッチの適用 |
| DB メンテナンス | 月次 | バキューム・統計情報更新・インデックス最適化 |
| 証明書更新 | 自動（cert-manager）+ 月次確認 | TLS 証明書の有効性維持 |
| シークレットローテーション | 四半期（90日毎） | 認証情報の定期更新によるセキュリティ強化 |
| Kubernetes バージョンアップ | 四半期〜半期 | AKS マネージドノードの更新 |
| 依存パッケージ更新 | 月次 | 脆弱性対応・機能改善 |

---

## メンテナンスウィンドウ設定

### 定期メンテナンスウィンドウ

| メンテナンス種別 | 実施タイミング | 時間帯 | 所要時間目安 |
|--------------|------------|--------|-----------|
| **通常メンテナンス** | **毎月第 3 日曜日** | **02:00〜04:00 JST** | 最大 2 時間 |
| 緊急パッチ適用 | 随時（セキュリティ緊急度に応じて） | 影響最小の時間帯 | 1 時間以内 |
| 大規模アップグレード | 四半期毎（別途調整） | 02:00〜06:00 JST | 最大 4 時間 |

### メンテナンスウィンドウ管理

```bash
# AKS メンテナンスウィンドウ設定（Azure CLI）
az aks update \
  --resource-group rg-ztid-prod \
  --name aks-ztid-prod \
  --maintenance-configuration-file maintenance-config.json

# maintenance-config.json の内容
cat <<EOF > maintenance-config.json
{
  "maintenanceWindow": {
    "schedule": {
      "weekly": {
        "dayOfWeek": "Sunday",
        "intervalWeeks": 4,
        "startTime": "02:00",
        "durationHours": 4
      }
    },
    "notAllowedDates": []
  }
}
EOF
```

### 通知スケジュール

| 通知タイミング | 通知先 | 内容 |
|-------------|--------|------|
| 1 週間前 | 全チーム + ステークホルダー | メンテナンス予告・影響範囲 |
| 前日 | 当番担当者 + チームリード | 最終確認・手順書共有 |
| 開始 30 分前 | 当番担当者 | 開始準備リマインダー |
| 開始時 | Slack #ops-maintenance | メンテナンス開始通知 |
| 終了時 | Slack #ops-maintenance + 全チーム | 完了通知・実施内容サマリー |

---

## OS・ミドルウェアパッチ適用手順

### パッチ適用の基本フロー

1. **パッチ情報収集**: Azure Security Center / CVE データベースで要対応パッチを確認
2. **優先度評価**: Critical > High > Medium の順で対応
3. **テスト環境適用**: 本番前にテスト環境で動作確認
4. **本番適用**: ローリングアップデートで無停止パッチ適用
5. **検証**: パッチ適用後の動作確認

### コンテナイメージのパッチ適用

```bash
#!/bin/bash
# コンテナイメージ更新スクリプト
set -e

REGISTRY="acrztidprod.azurecr.io"
NAMESPACE="ztid"
TIMESTAMP=$(date +%Y%m%d)

SERVICES=(
  "api-gateway"
  "auth-service"
  "user-service"
  "access-control-service"
  "celery-worker"
)

for SERVICE in "${SERVICES[@]}"; do
  echo "=== $SERVICE のイメージ更新 ==="

  # 現在のイメージタグ確認
  CURRENT_TAG=$(kubectl get deployment "$SERVICE" -n "$NAMESPACE" \
    -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
  echo "現在のタグ: $CURRENT_TAG"

  # 新しいイメージのビルド・プッシュ（CI/CD パイプラインが実行する想定）
  # ここでは手動更新の場合の例
  NEW_TAG="$(date +%Y%m%d)-patched"

  # イメージの更新
  kubectl set image deployment/"$SERVICE" \
    "$SERVICE=$REGISTRY/$SERVICE:$NEW_TAG" \
    -n "$NAMESPACE"

  # ロールアウト完了待機
  kubectl rollout status deployment/"$SERVICE" -n "$NAMESPACE" --timeout=300s

  echo "OK: $SERVICE 更新完了"
done

echo "=== 全サービスの更新完了 ==="
```

### Python パッケージ依存関係の更新

```bash
# 脆弱性のある依存パッケージを確認
pip-audit --require requirements.txt

# 安全なバージョンに更新
pip install --upgrade <package-name>

# requirements.txt の更新
pip freeze > requirements.txt

# Docker イメージ再ビルド
docker build -t acrztidprod.azurecr.io/api-gateway:$(date +%Y%m%d)-patched .
docker push acrztidprod.azurecr.io/api-gateway:$(date +%Y%m%d)-patched
```

---

## Kubernetes ノードメンテナンス

### ノードのドレイン（退避）手順

```bash
#!/bin/bash
# ノードメンテナンス手順
set -e

NODE_NAME="$1"
NAMESPACE="ztid"

if [ -z "$NODE_NAME" ]; then
  echo "使用方法: $0 <node-name>"
  echo "利用可能なノード:"
  kubectl get nodes -o wide
  exit 1
fi

echo "=== ノードメンテナンス開始: $NODE_NAME ==="

# 1. ノードの現在の状態確認
echo "[1] ノード状態確認"
kubectl describe node "$NODE_NAME" | grep -E "Conditions:|Taints:|Unschedulable:"

# 2. ノードをスケジュール不可にする（cordon）
echo "[2] ノードを cordon（新規 Pod スケジュール停止）"
kubectl cordon "$NODE_NAME"

# 3. ノードの Pod 一覧確認
echo "[3] 対象ノードの Pod 一覧"
kubectl get pods -A --field-selector spec.nodeName="$NODE_NAME"

# 4. ノードから Pod を退避（drain）
echo "[4] Pod を drain（既存 Pod の退避）"
kubectl drain "$NODE_NAME" \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --force \
  --grace-period=60 \
  --timeout=300s

echo "Pod 退避完了"

# 5. 退避確認
echo "[5] 退避後の確認"
kubectl get pods -A --field-selector spec.nodeName="$NODE_NAME"

echo "=== $NODE_NAME への Pod 退避完了。メンテナンスを実施してください。 ==="
echo "メンテナンス完了後、以下のコマンドでノードを復帰させてください："
echo "  kubectl uncordon $NODE_NAME"
```

### ノードの復帰手順

```bash
#!/bin/bash
# ノードメンテナンス後の復帰
NODE_NAME="$1"

# 1. ノードのスケジュール再開（uncordon）
echo "=== ノードを uncordon: $NODE_NAME ==="
kubectl uncordon "$NODE_NAME"

# 2. ノード状態の確認
echo "[確認] ノード状態"
kubectl get node "$NODE_NAME"

# 3. Pod の再スケジュール確認
echo "[確認] Pod の再スケジュール"
sleep 30
kubectl get pods -A --field-selector spec.nodeName="$NODE_NAME"

# 4. 全 Pod の正常稼働確認
echo "[確認] 全 Pod のステータス"
kubectl get pods -n ztid
```

### AKS ノードプールの更新

```bash
# AKS ノードプールの Kubernetes バージョン確認
az aks get-upgrades \
  --resource-group rg-ztid-prod \
  --name aks-ztid-prod \
  --output table

# ノードプールのアップグレード（ローリング更新）
az aks nodepool upgrade \
  --resource-group rg-ztid-prod \
  --cluster-name aks-ztid-prod \
  --name systempool \
  --kubernetes-version 1.30.0 \
  --no-wait

# アップグレード状態の監視
az aks nodepool show \
  --resource-group rg-ztid-prod \
  --cluster-name aks-ztid-prod \
  --name systempool \
  --query "{name:name, powerState:powerState.code, provisioningState:provisioningState, k8sVersion:currentOrchestratorVersion}" \
  --output table
```

### Pod Disruption Budget (PDB) の確認

```bash
# PDB の確認（メンテナンス前に全サービスで設定されていることを確認）
kubectl get pdb -n ztid

# PDB 設定例（最低 1 Pod の稼働を保証）
cat <<EOF | kubectl apply -f -
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: ztid
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api-gateway
EOF
```

---

## DB バキューム・ANALYZE 実行

### 自動バキューム設定確認

```sql
-- 自動バキューム設定の確認
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name LIKE '%autovacuum%'
ORDER BY name;

-- 最後にバキューム・ANALYZE が実行されたテーブルの確認
SELECT
  schemaname,
  tablename,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze,
  n_dead_tup AS dead_tuples,
  n_live_tup AS live_tuples,
  ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio_pct
FROM pg_stat_user_tables
ORDER BY dead_tuples DESC
LIMIT 20;
```

### 手動バキューム・ANALYZE 実行スクリプト

```bash
#!/bin/bash
# PostgreSQL 定期メンテナンススクリプト
set -e

DB_HOST="postgresql-primary.ztid.svc.cluster.local"
DB_NAME="ztid_prod"
DB_USER="postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/tmp/db_maintenance_${TIMESTAMP}.log"

echo "=== PostgreSQL メンテナンス開始: $(date) ===" | tee -a "$LOG_FILE"

# 1. デッドタプルが多いテーブルのバキューム
echo "[1] VACUUM ANALYZE 実行" | tee -a "$LOG_FILE"
kubectl exec -n ztid deploy/postgresql -- psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "VACUUM ANALYZE;" 2>&1 | tee -a "$LOG_FILE"

# 2. 肥大化したテーブルの VACUUM FULL（必要な場合のみ）
# ※ VACUUM FULL はテーブルロックが発生するため、低負荷時のみ実施
echo "[2] 肥大化テーブルの確認" | tee -a "$LOG_FILE"
kubectl exec -n ztid deploy/postgresql -- psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS total_size,
  pg_size_pretty(pg_relation_size(tablename::regclass)) AS table_size,
  ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;
" 2>&1 | tee -a "$LOG_FILE"

# 3. インデックスの再構築（肥大化している場合）
echo "[3] インデックス状態確認" | tee -a "$LOG_FILE"
kubectl exec -n ztid deploy/postgresql -- psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
ORDER BY pg_relation_size(indexname::regclass) DESC
LIMIT 20;
" 2>&1 | tee -a "$LOG_FILE"

# 4. 統計情報の更新
echo "[4] ANALYZE 実行（全テーブル）" | tee -a "$LOG_FILE"
kubectl exec -n ztid deploy/postgresql -- psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "ANALYZE VERBOSE;" 2>&1 | tee -a "$LOG_FILE"

# 5. 長時間トランザクションの確認
echo "[5] 長時間実行クエリの確認" | tee -a "$LOG_FILE"
kubectl exec -n ztid deploy/postgresql -- psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
  AND state != 'idle';
" 2>&1 | tee -a "$LOG_FILE"

echo "=== PostgreSQL メンテナンス完了: $(date) ===" | tee -a "$LOG_FILE"

# ログをアップロード
az storage blob upload \
  --account-name stztidprodbackup \
  --container-name maintenance-logs \
  --name "db_maintenance_${TIMESTAMP}.log" \
  --file "$LOG_FILE"

echo "ログを保存しました: $LOG_FILE"
```

---

## SSL証明書更新手順

### cert-manager による自動更新（推奨）

```yaml
# cert-manager ClusterIssuer 設定（Let's Encrypt / Azure Key Vault）
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

```yaml
# Certificate リソースの定義
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ztid-tls
  namespace: ztid
spec:
  secretName: ztid-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.ztid.example.com
    - console.ztid.example.com
    - grafana.ztid.example.com
  duration: 2160h      # 90 日
  renewBefore: 720h    # 期限切れ 30 日前に自動更新
```

### 証明書状態確認

```bash
# cert-manager 管理の証明書状態確認
kubectl get certificates -A
kubectl describe certificate ztid-tls -n ztid

# 証明書の詳細（有効期限確認）
kubectl get secret ztid-tls-secret -n ztid -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -enddate -subject

# cert-manager のログ確認
kubectl logs -n cert-manager deploy/cert-manager --tail=50
```

### 手動での証明書更新（cert-manager 以外の場合）

```bash
#!/bin/bash
# SSL 証明書手動更新スクリプト
set -e

DOMAIN="api.ztid.example.com"
CERT_DIR="/tmp/certs"
NAMESPACE="ztid"
SECRET_NAME="ztid-tls-secret"

mkdir -p "$CERT_DIR"

echo "=== SSL 証明書更新: $DOMAIN ==="

# 1. 現在の証明書有効期限確認
echo "[1] 現在の証明書確認"
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -enddate

# 2. 新しい証明書の取得（Azure Key Vault から）
echo "[2] Azure Key Vault から証明書取得"
az keyvault certificate download \
  --vault-name kv-ztid-prod \
  --name ztid-api-cert \
  --file "$CERT_DIR/tls.crt" \
  --encoding PEM

az keyvault secret show \
  --vault-name kv-ztid-prod \
  --name ztid-api-cert \
  --query "value" -o tsv | openssl pkcs12 -nocerts -nodes -out "$CERT_DIR/tls.key" \
  -passin pass: 2>/dev/null || true

# 3. Kubernetes Secret の更新
echo "[3] Kubernetes Secret 更新"
kubectl create secret tls "$SECRET_NAME" \
  --cert="$CERT_DIR/tls.crt" \
  --key="$CERT_DIR/tls.key" \
  -n "$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Ingress の確認（自動で新しい Secret を使用）
echo "[4] Ingress 確認"
kubectl get ingress -n "$NAMESPACE"

# 5. 新しい証明書の有効期限確認
echo "[5] 更新後の証明書確認"
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -enddate

# クリーンアップ
rm -rf "$CERT_DIR"
echo "=== SSL 証明書更新完了 ==="
```

---

## シークレット・APIキーのローテーション

### ローテーション対象と頻度

| シークレット種別 | ローテーション頻度 | 自動化 | 担当 |
|--------------|----------------|--------|------|
| DB パスワード（アプリ用） | 90 日毎 | 半自動（ローテーションスクリプト） | インフラチーム |
| DB パスワード（管理者用） | 30 日毎 | 手動 | DBA |
| Redis AUTH パスワード | 90 日毎 | 半自動 | インフラチーム |
| API キー（外部サービス連携） | 180 日毎 または 漏洩時 | 手動 | 開発チーム |
| JWT 署名キー | 90 日毎 | 半自動 | セキュリティチーム |
| Azure サービスプリンシパル | 90 日毎 | Azure AD による自動 | インフラチーム |
| Webhook シークレット | 180 日毎 | 手動 | 開発チーム |

### DB パスワードのローテーション手順

```bash
#!/bin/bash
# PostgreSQL パスワードローテーションスクリプト
set -e

NAMESPACE="ztid"
VAULT_NAME="kv-ztid-prod"
DB_HOST="postgresql-primary.ztid.svc.cluster.local"
DB_USER="ztid_app"
SECRET_NAME="ztid-db-credentials"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== DB パスワードローテーション開始: $TIMESTAMP ==="

# 1. 新しいパスワード生成（32 文字）
NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '=/+' | head -c 32)

# 2. PostgreSQL のパスワード変更
echo "[1] PostgreSQL パスワード変更"
kubectl exec -n "$NAMESPACE" deploy/postgresql -- psql \
  -U postgres \
  -c "ALTER USER $DB_USER WITH PASSWORD '$NEW_PASSWORD';"

# 3. Azure Key Vault シークレットの更新
echo "[2] Azure Key Vault シークレット更新"
az keyvault secret set \
  --vault-name "$VAULT_NAME" \
  --name "db-password-app" \
  --value "$NEW_PASSWORD" \
  --tags "rotated_at=$TIMESTAMP"

# 4. Kubernetes Secret の更新
echo "[3] Kubernetes Secret 更新"
kubectl patch secret "$SECRET_NAME" -n "$NAMESPACE" \
  --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/DB_PASSWORD\", \"value\": \"$(echo -n "$NEW_PASSWORD" | base64)\"}]"

# 5. アプリケーションの再起動（新しいシークレットを読み込ませる）
echo "[4] アプリケーション再起動"
kubectl rollout restart deployment/api-gateway -n "$NAMESPACE"
kubectl rollout restart deployment/auth-service -n "$NAMESPACE"
kubectl rollout restart deployment/user-service -n "$NAMESPACE"

# 6. 再起動完了待機と確認
echo "[5] 再起動完了確認"
kubectl rollout status deployment/api-gateway -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/auth-service -n "$NAMESPACE" --timeout=300s

# 7. DB 接続確認
echo "[6] DB 接続確認"
kubectl exec -n "$NAMESPACE" deploy/api-gateway -- python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('DB 接続OK:', conn.get_dsn_parameters())
conn.close()
"

echo "=== DB パスワードローテーション完了 ==="
```

### JWT 署名キーのローテーション手順

```bash
#!/bin/bash
# JWT 署名キーローテーション（ゼロダウンタイム方式）
# 古いキーと新しいキーを一定期間並行運用する

NAMESPACE="ztid"
VAULT_NAME="kv-ztid-prod"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== JWT 署名キーローテーション開始 ==="

# 1. 新しい RSA キーペアを生成
echo "[1] 新しいキーペアを生成"
openssl genrsa -out /tmp/jwt_private_new.pem 4096
openssl rsa -in /tmp/jwt_private_new.pem -pubout -out /tmp/jwt_public_new.pem

# 2. 現在の検証キーセットに新しいキーを追加（JWKS 形式）
echo "[2] JWKS に新しいキーを追加（移行期間: 新旧両方のキーを有効化）"
# ※ 実際の実装では JWKS エンドポイントへの反映が必要

# 3. Azure Key Vault に新しいキーを保存
echo "[3] Azure Key Vault への新しいキーの保存"
az keyvault secret set \
  --vault-name "$VAULT_NAME" \
  --name "jwt-private-key-new" \
  --file /tmp/jwt_private_new.pem \
  --tags "created_at=$TIMESTAMP"

az keyvault secret set \
  --vault-name "$VAULT_NAME" \
  --name "jwt-public-key-new" \
  --file /tmp/jwt_public_new.pem

# 4. アプリケーションを新しいキーで署名するよう更新
echo "[4] アプリケーション設定更新（新しいキーで署名・旧キーも検証用に保持）"
kubectl set env deployment/auth-service \
  JWT_SIGNING_KEY_VERSION="new" \
  -n "$NAMESPACE"

kubectl rollout status deployment/auth-service -n "$NAMESPACE" --timeout=300s

echo "移行期間: 7日間、新旧キーを並行運用します"
echo "7日後に古いキーを無効化してください: jwt-private-key-old"

# クリーンアップ
rm -f /tmp/jwt_private_new.pem /tmp/jwt_public_new.pem

echo "=== JWT 署名キーローテーション完了 ==="
```

### External Secrets Operator によるシークレット自動同期

```yaml
# ExternalSecret リソース（Azure Key Vault からの自動同期）
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ztid-secrets
  namespace: ztid
spec:
  refreshInterval: 1h  # 1時間毎に Azure Key Vault と同期
  secretStoreRef:
    name: azure-keyvault-store
    kind: ClusterSecretStore
  target:
    name: ztid-app-secrets
    creationPolicy: Owner
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: db-password-app
    - secretKey: REDIS_PASSWORD
      remoteRef:
        key: redis-auth-password
    - secretKey: JWT_SECRET_KEY
      remoteRef:
        key: jwt-secret-key
```

---

## メンテナンス前後チェックリスト

### メンテナンス前チェックリスト

```
=== メンテナンス前チェックリスト ===
実施日時: YYYY-MM-DD HH:MM JST
担当者  : [氏名]
メンテナンス内容: [概要]

■ 通知確認
[ ] メンテナンス通知を 1 週間前に全ステークホルダーへ送付済み
[ ] ステータスページにメンテナンス予定を掲載済み
[ ] 当番担当者に手順書を共有済み

■ バックアップ確認
[ ] PostgreSQL フルバックアップ（直近 24 時間以内）の成功を確認
[ ] Redis スナップショット（直近 24 時間以内）の成功を確認
[ ] Kubernetes 設定バックアップ（直近 24 時間以内）の成功を確認
[ ] バックアップからのリストア手順を確認済み

■ システム状態確認
[ ] 全 Pod が Running 状態であることを確認
[ ] アラートが発生していないことを確認
[ ] CPU / メモリ使用率が正常範囲内であることを確認
[ ] 直近 24 時間のエラーレートが正常であることを確認
[ ] Celery キューに積み残しがないことを確認

■ ロールバック計画確認
[ ] 問題発生時のロールバック手順を確認済み
[ ] ロールバック判断の閾値を確認済み（例: 15 分以内に復旧できない場合）
[ ] ロールバック実施権限者を確認済み

■ 連絡体制確認
[ ] 緊急連絡先一覧を準備
[ ] インシデント対応チームの待機確認
[ ] エスカレーション先を確認済み

■ 作業環境確認
[ ] 必要な CLI ツールが使用可能（kubectl / az / psql）
[ ] Azure Portal へのアクセスを確認
[ ] Grafana / Prometheus へのアクセスを確認
```

### メンテナンス後チェックリスト

```
=== メンテナンス後チェックリスト ===
実施完了日時: YYYY-MM-DD HH:MM JST
担当者      : [氏名]
実施内容    : [概要]

■ サービス稼働確認
[ ] 全 Pod が Running / Ready 状態であることを確認
  実行コマンド: kubectl get pods -n ztid
  結果: [記録]

[ ] 全 API ヘルスチェックエンドポイントが 200 を返すことを確認
  確認 URL: https://api.ztid.example.com/health
  結果: [記録]

[ ] 認証サービスの動作確認（テストアカウントでログイン）
  結果: [記録]

■ パフォーマンス確認（作業前との比較）
[ ] API p95 レスポンスタイムが正常範囲内（< 200ms）
  Grafana: [URL]
  結果: [ms]

[ ] エラーレートが正常範囲内（< 0.5%）
  結果: [%]

[ ] CPU / メモリ使用率が正常範囲内
  CPU: [%] / メモリ: [%]

■ データ整合性確認
[ ] DB への接続と基本クエリの動作確認
  実行コマンド: kubectl exec -n ztid deploy/postgresql -- psql -U postgres -d ztid_prod -c "SELECT COUNT(*) FROM users;"
  結果: [件数]

[ ] Redis 接続確認
  実行コマンド: kubectl exec -n ztid deploy/redis -- redis-cli PING
  結果: [PONG]

■ 監視確認
[ ] Prometheus がメトリクスを収集していることを確認
[ ] Grafana ダッシュボードが正常に表示されることを確認
[ ] AlertManager が正常に動作していることを確認

■ 作業記録
作業開始時刻: HH:MM JST
作業終了時刻: HH:MM JST
総作業時間  : X 時間 Y 分

実施内容の詳細:
[実施した作業の詳細を記録]

■ 問題・対処事項
（発生した問題と対処内容を記録）

■ 次回メンテナンスへの申し送り
（次回担当者への申し送り事項を記録）

■ ステータスページ更新
[ ] メンテナンス完了をステータスページに反映済み
[ ] 完了通知を Slack #ops-maintenance に投稿済み
[ ] 関係者への完了メールを送付済み
```

### 緊急ロールバック判断基準

| 状況 | ロールバック判断 | 実施手順 |
|------|------------|---------|
| 主要 API が応答しない（5 分以上） | 即時ロールバック | `kubectl rollout undo deployment/<name> -n ztid` |
| エラーレートが 5% 超（10 分以上） | ロールバック検討 | 原因調査後、改善見込みなければロールバック |
| DB 接続エラーが多発 | 即時ロールバック | DB 設定を元に戻し、接続確認 |
| セキュリティアラートが発生 | 即時ロールバック + インシデント宣言 | インシデント対応手順書参照 |
| 15 分以内に復旧の見込みなし | ロールバック実施 | ステークホルダーへ通知後ロールバック |

---

*本文書の改訂履歴は Git コミット履歴で管理します。*
