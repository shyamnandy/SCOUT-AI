"""Celery tasks for automated newsletter generation and dispatch.

Delivery runs in two phases so content is fresh but ready on time:

  T-5min  curate_topic_for_slot  → search/scrape/summarize, save a draft
  T       dispatch_slot          → send every draft for that user+slot

A 5-minute lead is generous for the pipeline itself (a real run measures
~20-90s), but a short lead can still land after the curate window has
already passed relative to the beat tick — e.g. a topic created 2 minutes
before its own slot. dispatch_slot self-heals that case: if a due topic
has no draft yet when its slot arrives, it curates synchronously right
there instead of silently skipping delivery.

Progress is tracked per (topic, slot, local date), so a topic scheduled at
08:00, 14:00 and 22:00 delivers three times a day with different content.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from worker.celery_app import celery_app

# How long before a delivery slot curation starts.
CURATE_LEAD_MINUTES = 5
# Beat runs every 5 minutes; match the matching tolerance to that.
WINDOW_MINUTES = 5


def _get_sync_db():
    """Get a synchronous MongoDB client for Celery tasks."""
    import certifi
    from pymongo import MongoClient
    from app.config import get_settings
    settings = get_settings()
    # Certificate verification stays on — see app/database.py.
    client = MongoClient(
        settings.MONGO_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
    )
    return client[settings.DB_NAME]


def _run_async(coro):
    """Helper to run async functions from sync Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _local_now(topic: dict, now_utc: datetime) -> datetime:
    """Convert UTC to the topic's configured local time."""
    try:
        import pytz
        return now_utc.astimezone(pytz.timezone(topic.get("timezone", "Asia/Kolkata")))
    except Exception:
        return now_utc


def _match_window(
    local_now: datetime,
    slot: str,
    offset_minutes: int,
    window_minutes: int = WINDOW_MINUTES,
) -> str | None:
    """
    Check whether `local_now` falls within the trigger window for `slot`.

    The trigger is `slot - offset_minutes`. Candidate days span -1/0/+1 so
    windows that straddle midnight (e.g. curating a 00:10 slot at 23:50)
    resolve to the correct delivery date.

    Returns the delivery date as an ISO date string, or None.
    """
    try:
        hour, minute = map(int, slot.split(":"))
    except (ValueError, AttributeError):
        return None

    for day_delta in (-1, 0, 1):
        candidate = (local_now + timedelta(days=day_delta)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        trigger = candidate - timedelta(minutes=offset_minutes)
        if abs((local_now - trigger).total_seconds()) <= window_minutes * 60:
            return candidate.date().isoformat()
    return None


@celery_app.task(name="worker.tasks.check_and_dispatch_newsletters")
def check_and_dispatch_newsletters():
    """
    Periodic scheduler (every 5 min via Celery Beat).

    Enqueues curation CURATE_LEAD_MINUTES ahead of each slot, and dispatch
    at the slot itself. Both downstream tasks are idempotent, so overlapping
    windows can't double-send.
    """
    db = _get_sync_db()
    now_utc = datetime.now(timezone.utc)

    active_topics = list(db.topics.find({"is_active": True}))

    curated = 0
    dispatched = 0
    expired = 0
    seen_dispatch = set()

    for topic in active_topics:
        # Retire ephemeral topics whose end date has passed.
        if topic.get("lifecycle") == "ephemeral" and topic.get("expiration_date"):
            exp = topic["expiration_date"]
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now_utc:
                db.topics.update_one({"_id": topic["_id"]}, {"$set": {"is_active": False}})
                expired += 1
                continue

        local_now = _local_now(topic, now_utc)
        topic_id = str(topic["_id"])

        for slot in topic.get("delivery_times", []):
            # Phase 1 — curate ahead of time, once per slot per day.
            curate_date = _match_window(local_now, slot, CURATE_LEAD_MINUTES)
            if curate_date and not db.newsletters.find_one(
                {"topic_id": topic_id, "slot": slot, "local_date": curate_date}
            ):
                # .apply() runs in-process (no broker needed) so this scheduler
                # works whether or not Celery/Redis are actually deployed.
                curate_topic_for_slot.apply(args=(topic_id, slot, curate_date))
                curated += 1

            # Phase 2 — dispatch everything queued for this user+slot.
            send_date = _match_window(local_now, slot, 0)
            if send_date:
                key = (topic["user_id"], slot, send_date)
                if key not in seen_dispatch:
                    seen_dispatch.add(key)
                    dispatch_slot.apply(args=(topic["user_id"], slot, send_date))
                    dispatched += 1

    return {
        "checked": len(active_topics),
        "curation_jobs": curated,
        "dispatch_jobs": dispatched,
        "expired": expired,
        "timestamp": now_utc.isoformat(),
    }


def _curate_and_save(db, topic: dict, user: dict, slot: str | None, local_date: str | None) -> bool:
    """Run the pipeline for one topic and persist the draft. Returns True if a draft was produced."""
    from pymongo.errors import DuplicateKeyError
    from app.services.pipeline import curate_topic, build_draft_doc

    payload = _run_async(curate_topic(topic, user))
    if not payload:
        return False
    try:
        db.newsletters.insert_one(build_draft_doc(topic, user, payload, slot, local_date))
    except DuplicateKeyError:
        # Scheduled curation landed first (race with a self-heal call) — fine, draft exists.
        pass
    return True


@celery_app.task(name="worker.tasks.curate_topic_for_slot", bind=True, max_retries=2)
def curate_topic_for_slot(self, topic_id: str, slot: str, local_date: str):
    """Curate one topic for one delivery slot and store it as a draft."""
    try:
        db = _get_sync_db()

        topic = db.topics.find_one({"_id": ObjectId(topic_id)})
        if not topic or not topic.get("is_active"):
            return {"status": "skipped", "reason": "Topic inactive or missing"}

        # Guard against a duplicate enqueue landing between check and run.
        if db.newsletters.find_one({"topic_id": topic_id, "slot": slot, "local_date": local_date}):
            return {"status": "skipped", "reason": "Already curated for this slot"}

        user = db.users.find_one({"_id": ObjectId(topic["user_id"])})
        if not user:
            return {"status": "skipped", "reason": "User not found"}

        if not _curate_and_save(db, topic, user, slot, local_date):
            return {"status": "failed", "reason": "No usable content"}

        print(f"[curate] Draft ready: '{topic['name']}' @ {slot} ({local_date})")
        return {"status": "success", "topic": topic["name"], "slot": slot}

    except Exception as exc:
        print(f"Curation failed for topic {topic_id} @ {slot}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="worker.tasks.dispatch_slot", bind=True, max_retries=2)
def dispatch_slot(self, user_id: str, slot: str, local_date: str):
    """
    Send every draft queued for this user's slot.

    With batching on (the default), topics sharing a slot go out as one
    combined email; otherwise each topic is sent separately.
    """
    try:
        from app.services.curator_service import render_batch_newsletter
        from app.services.email_service import send_newsletter_email
        from app.services.crypto_service import decrypt

        db = _get_sync_db()
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return {"status": "skipped", "reason": "User not found"}

        # A user's own Resend key, if set — lets them receive mail without
        # the shared app-level key's sandbox recipient restriction.
        resend_api_key = decrypt(user.get("resend_api_key"))

        # Self-heal: a topic due this slot with no draft yet (short lead time,
        # a missed curate window, worker downtime) gets curated right now
        # instead of silently being left out of the send.
        due_topics = list(db.topics.find({
            "user_id": user_id,
            "is_active": True,
            "delivery_times": slot,
        }))
        already_curated = {
            d["topic_id"]
            for d in db.newsletters.find(
                {"user_id": user_id, "slot": slot, "local_date": local_date},
                {"topic_id": 1},
            )
        }
        for topic in due_topics:
            if str(topic["_id"]) in already_curated:
                continue
            print(f"[dispatch] Late curation for '{topic['name']}' @ {slot} — no draft yet")
            _curate_and_save(db, topic, user, slot, local_date)

        drafts = list(db.newsletters.find({
            "user_id": user_id,
            "slot": slot,
            "local_date": local_date,
            "delivery_status": "draft",
        }))
        if not drafts:
            return {"status": "skipped", "reason": "Nothing queued for this slot"}

        batch = user.get("batch_delivery", True)
        slot_label = _slot_label(slot)
        sent_at = datetime.now(timezone.utc)

        if batch and len(drafts) > 1:
            html = render_batch_newsletter(
                sections=[{"topic_name": d["topic_name"], "articles": d["articles"]} for d in drafts],
                user_name=user["name"],
                slot_label=slot_label,
            )
            subject = f"Your ScoutAI Digest — {len(drafts)} updates ({slot_label})"
            result = _run_async(send_newsletter_email(user["email"], subject, html, resend_api_key))
            _finalize(db, drafts, result["status"], sent_at, batch_html=html)
            delivered = 1
        else:
            for draft in drafts:
                subject = f"{draft['topic_name']} — Your ScoutAI Update"
                result = _run_async(
                    send_newsletter_email(user["email"], subject, draft["html_content"], resend_api_key)
                )
                _finalize(db, [draft], result["status"], sent_at)
            delivered = len(drafts)

        print(f"[dispatch] {len(drafts)} draft(s) sent to {user['email']} @ {slot}")

        return {
            "status": "success",
            "emails_sent": delivered,
            "topics": len(drafts),
            "batched": bool(batch and len(drafts) > 1),
        }

    except Exception as exc:
        print(f"Dispatch failed for user {user_id} @ {slot}: {exc}")
        raise self.retry(exc=exc, countdown=60)


def _finalize(db, drafts: list[dict], status: str, sent_at: datetime, batch_html: str | None = None):
    """Mark drafts as sent/failed and stamp the topics' last delivery."""
    update = {"delivery_status": status, "delivered_at": sent_at}
    if batch_html:
        # Store what was actually emailed so History shows the real thing.
        update["batch_html"] = batch_html

    db.newsletters.update_many(
        {"_id": {"$in": [d["_id"] for d in drafts]}},
        {"$set": update},
    )
    if status == "sent":
        db.topics.update_many(
            {"_id": {"$in": [ObjectId(d["topic_id"]) for d in drafts]}},
            {"$set": {"last_delivered_at": sent_at}},
        )


def _slot_label(slot: str) -> str:
    """'14:00' → '2:00 PM'."""
    try:
        hour, minute = map(int, slot.split(":"))
        suffix = "AM" if hour < 12 else "PM"
        hour12 = 12 if hour % 12 == 0 else hour % 12
        return f"{hour12}:{minute:02d} {suffix}"
    except Exception:
        return slot
