"""Idempotent schema migration for the ScoutAI Atlas database.

MongoDB is schemaless, so "migration" here means backfilling fields that
newer code expects onto documents written by older code, and making sure
indexes exist. Safe to run repeatedly.

    python -m scripts.migrate            # apply
    python -m scripts.migrate --dry-run  # report only
"""

import sys

import certifi
from pymongo import MongoClient

from app.config import get_settings

DEFAULT_SLOT = "08:00"
CHAT_SESSION_TTL_SECONDS = 24 * 60 * 60


def get_db():
    settings = get_settings()
    client = MongoClient(
        settings.MONGO_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    return client[settings.DB_NAME]


def migrate(dry_run: bool = False) -> None:
    db = get_db()
    tag = "[dry-run] would" if dry_run else "[apply]"

    # --- users: batch_delivery ------------------------------------------
    q = {"batch_delivery": {"$exists": False}}
    n = db.users.count_documents(q)
    print(f"{tag} set batch_delivery=True on {n} user(s)")
    if n and not dry_run:
        db.users.update_many(q, {"$set": {"batch_delivery": True}})

    # --- users: delivery_slots, seeded from their topics' existing times --
    q = {"delivery_slots": {"$exists": False}}
    users = list(db.users.find(q, {"_id": 1}))
    print(f"{tag} seed delivery_slots on {len(users)} user(s)")
    for user in users:
        uid = str(user["_id"])
        times = {
            t
            for doc in db.topics.find({"user_id": uid}, {"delivery_times": 1})
            for t in doc.get("delivery_times", [])
        }
        slots = sorted(times) or [DEFAULT_SLOT]
        print(f"    {uid} -> {slots}")
        if not dry_run:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"delivery_slots": slots}})

    # --- users: stuck onboarding — has topics but flag never flipped ------
    # (older code only set is_onboarded via the "Go to Dashboard" button;
    # leaving the flow any other way left users with real topics stuck
    # being redirected back to onboarding forever)
    unfinished = list(db.users.find({"is_onboarded": {"$ne": True}}, {"_id": 1, "email": 1}))
    fixed = 0
    for user in unfinished:
        if db.topics.count_documents({"user_id": str(user["_id"])}) > 0:
            print(f"{tag} mark is_onboarded=True for {user['email']} (has topics, flag was stuck)")
            fixed += 1
            if not dry_run:
                db.users.update_one({"_id": user["_id"]}, {"$set": {"is_onboarded": True}})
    if not fixed:
        print(f"{tag} fix stuck-onboarding users: none found")

    # --- topics: normalise missing delivery_times to [] -------------------
    q = {"delivery_times": {"$exists": False}}
    n = db.topics.count_documents(q)
    print(f"{tag} set delivery_times=[] on {n} topic(s)")
    if n and not dry_run:
        db.topics.update_many(q, {"$set": {"delivery_times": []}})

    # --- newsletters: tag pre-slot docs so dispatch never picks them up ---
    q = {"slot": {"$exists": False}}
    n = db.newsletters.count_documents(q)
    print(f"{tag} set slot=None/local_date=None on {n} legacy newsletter(s)")
    if n and not dry_run:
        db.newsletters.update_many(q, {"$set": {"slot": None, "local_date": None}})

    q = {"delivery_status": {"$exists": False}}
    n = db.newsletters.count_documents(q)
    print(f"{tag} set delivery_status='sent' on {n} untagged newsletter(s)")
    if n and not dry_run:
        db.newsletters.update_many(q, {"$set": {"delivery_status": "sent"}})

    # --- indexes ---------------------------------------------------------
    print(f"{tag} ensure indexes")
    if not dry_run:
        db.users.create_index("email", unique=True)
        db.topics.create_index("user_id")
        db.topics.create_index([("user_id", 1), ("is_active", 1)])
        db.newsletters.create_index([("user_id", 1), ("delivered_at", -1)])
        db.newsletters.create_index("topic_id")
        db.newsletters.create_index(
            [("topic_id", 1), ("slot", 1), ("local_date", 1)],
            unique=True,
            partialFilterExpression={"slot": {"$type": "string"}},
        )
        db.newsletters.create_index(
            [("user_id", 1), ("slot", 1), ("local_date", 1), ("delivery_status", 1)]
        )
        # Abandoned onboarding chats clean themselves up after a day.
        db.chat_sessions.create_index("created_at", expireAfterSeconds=CHAT_SESSION_TTL_SECONDS)

    print("\nDone." if not dry_run else "\nDry run complete — nothing written.")


if __name__ == "__main__":
    migrate(dry_run="--dry-run" in sys.argv)
