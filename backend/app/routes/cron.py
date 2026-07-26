"""External-cron-triggered scheduler tick.

Stands in for Celery Beat in production: an external free scheduler
(e.g. cron-job.org) POSTs here every 5 minutes instead of a Beat process
polling internally. worker.tasks now dispatches via `.apply()` (in-process,
no broker), so this endpoint needs no Redis or Celery worker running.
"""

from fastapi import APIRouter, Header, HTTPException
from app.config import get_settings

router = APIRouter(prefix="/api/cron", tags=["Cron"])


@router.get("/debug")
def debug_secret(x_cron_secret: str = Header(default="")):
    """Temporary: confirms what the running process actually loaded, without
    exposing either secret's real value. Remove once /tick auth is verified."""
    settings = get_settings()
    configured = settings.CRON_SECRET
    return {
        "configured_secret_set": bool(configured),
        "configured_secret_length": len(configured),
        "received_header_length": len(x_cron_secret),
        "match": bool(configured) and x_cron_secret == configured,
    }


@router.post("/tick")
def run_tick(x_cron_secret: str = Header(default="")):
    settings = get_settings()
    if not settings.CRON_SECRET or x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing cron secret")

    from worker.tasks import check_and_dispatch_newsletters
    return check_and_dispatch_newsletters()
