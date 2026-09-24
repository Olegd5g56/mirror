from celery import Celery

from app.config import settings

celery_app = Celery(
    "mirror",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.tz,
    enable_utc=True,
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Великі ролики (сотні МБ, crf 18) — не вбивати на 15 хвилинах.
    task_soft_time_limit=1800,
    task_time_limit=2100,
)

import app.tasks.media_processing  # noqa: E402, F401
