"""Delivery time slot routes.

Slots are the columns on the dashboard that topics get dragged into.
The canonical list lives on the user document; a topic is "in" a slot
when that time appears in its own `delivery_times`.
"""

import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import users_collection, topics_collection
from app.utils import get_current_user
from bson import ObjectId

router = APIRouter(prefix="/api/slots", tags=["Delivery Slots"])

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SlotRequest(BaseModel):
    time: str


async def _get_slots(user_id: str) -> list[str]:
    """Read a user's slots, seeding from existing topics on first access."""
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    slots = user.get("delivery_slots") if user else None

    if slots is None:
        # Migration path: derive slots from whatever the user's topics already use.
        cursor = topics_collection.find({"user_id": user_id})
        existing = {t for doc in await cursor.to_list(length=200) for t in doc.get("delivery_times", [])}
        slots = sorted(existing) or ["08:00"]
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"delivery_slots": slots}},
        )

    return sorted(slots)


@router.get("", response_model=list[str])
async def list_slots(user: dict = Depends(get_current_user)):
    """List the user's delivery time slots."""
    return await _get_slots(user["id"])


@router.post("", response_model=list[str])
async def add_slot(data: SlotRequest, user: dict = Depends(get_current_user)):
    """Create a new delivery time slot."""
    if not TIME_RE.match(data.time):
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format")

    slots = await _get_slots(user["id"])
    if data.time in slots:
        raise HTTPException(status_code=400, detail="That time slot already exists")

    slots = sorted(slots + [data.time])
    await users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"delivery_slots": slots}},
    )
    return slots


@router.put("/{slot_time}", response_model=list[str])
async def update_slot(slot_time: str, data: SlotRequest, user: dict = Depends(get_current_user)):
    """Rename a slot's time, carrying over every topic scheduled at the old time."""
    if not TIME_RE.match(data.time):
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format")

    slots = await _get_slots(user["id"])
    if slot_time not in slots:
        raise HTTPException(status_code=404, detail="Slot not found")
    if data.time == slot_time:
        return slots
    if data.time in slots:
        raise HTTPException(status_code=400, detail="That time slot already exists")

    slots = sorted([s for s in slots if s != slot_time] + [data.time])
    await users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"delivery_slots": slots}},
    )
    # Topics scheduled at the old time move to the new time.
    await topics_collection.update_many(
        {"user_id": user["id"], "delivery_times": slot_time},
        {"$addToSet": {"delivery_times": data.time}},
    )
    await topics_collection.update_many(
        {"user_id": user["id"]},
        {"$pull": {"delivery_times": slot_time}},
    )
    return slots


@router.delete("/{slot_time}", response_model=list[str])
async def delete_slot(slot_time: str, user: dict = Depends(get_current_user)):
    """Delete a slot and unschedule it from every topic that used it."""
    slots = await _get_slots(user["id"])
    if slot_time not in slots:
        raise HTTPException(status_code=404, detail="Slot not found")

    slots = [s for s in slots if s != slot_time]
    await users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"delivery_slots": slots}},
    )
    # Topics left with no times fall back into the unscheduled pool.
    await topics_collection.update_many(
        {"user_id": user["id"]},
        {"$pull": {"delivery_times": slot_time}},
    )
    return slots
