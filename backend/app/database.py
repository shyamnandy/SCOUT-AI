"""MongoDB async connection using motor."""

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

# Verify the Atlas server certificate against certifi's CA bundle. Never use
# tlsInsecure/tlsAllowInvalidCertificates here — that disables certificate and
# hostname checks, letting anyone who can intercept the connection impersonate
# the database and capture credentials.
client = AsyncIOMotorClient(
    settings.MONGO_URI,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)
db = client[settings.DB_NAME]

# Collections
users_collection = db["users"]
topics_collection = db["topics"]
newsletters_collection = db["newsletters"]
chat_sessions_collection = db["chat_sessions"]


async def init_indexes():
    """Create database indexes on startup."""
    await users_collection.create_index("email", unique=True)
    await topics_collection.create_index("user_id")
    await topics_collection.create_index([("user_id", 1), ("is_active", 1)])
    await newsletters_collection.create_index([("user_id", 1), ("delivered_at", -1)])
    await newsletters_collection.create_index("topic_id")
    # One draft per topic per slot per day — the guard against double curation.
    # Partial so manually triggered newsletters (slot: null) are exempt.
    await newsletters_collection.create_index(
        [("topic_id", 1), ("slot", 1), ("local_date", 1)],
        unique=True,
        partialFilterExpression={"slot": {"$type": "string"}},
    )
    # Dispatch lookup: every draft queued for a user's slot on a given day.
    await newsletters_collection.create_index(
        [("user_id", 1), ("slot", 1), ("local_date", 1), ("delivery_status", 1)]
    )
