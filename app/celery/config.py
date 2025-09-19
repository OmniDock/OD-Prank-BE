from __future__ import annotations

from celery import Celery
from app.core.config import settings


def _create_celery() -> Celery:
    app = Celery(
        "od_prank",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=[
            "app.celery.tasks.tts",
        ],
    )

    app.conf.update(
        task_always_eager=False,
        broker_connection_retry_on_startup=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_ignore_result=True,
    )
    return app


celery_app = _create_celery()