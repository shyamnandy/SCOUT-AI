"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "scoutai_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["worker.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Beat schedule — check for due newsletters every 5 minutes
celery_app.conf.beat_schedule = {
    "check-newsletter-dispatch": {
        "task": "worker.tasks.check_and_dispatch_newsletters",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}
