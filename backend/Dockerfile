FROM python:3.12-slim AS builder

WORKDIR /app

# ビルド依存パッケージ（wheels 生成に必要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ===================================
# 本番実行ステージ（軽量イメージ）
# ===================================
FROM python:3.12-slim AS runner

WORKDIR /app

# ランタイム依存パッケージのみ
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# builder ステージの wheels から pip インストール（ビルドツール不要）
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

COPY . .

# 非 root ユーザで実行（セキュリティ強化）
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
