"""
Celery アプリケーション設定
"""

from celery import Celery

from core.config import settings

celery_app = Celery(
    "ztid_governance",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.provisioning",
        "tasks.review",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    # タスクの再試行設定
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat スケジュール（定期実行）
    beat_schedule={
        "quarterly-account-review": {
            "task": "tasks.review.start_quarterly_review",
            "schedule": 60 * 60 * 24 * 90,  # 90日ごと（四半期）
        },
    },
)
