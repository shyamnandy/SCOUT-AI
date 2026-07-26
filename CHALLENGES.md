# Challenges

Engineering problems hit while building ScoutAI, and how they were solved. Kept concise for interview prep.

---

## 1. Always-on infra cost for scheduled newsletter delivery

**Problem:** Newsletter delivery times are freeform per-user (any `HH:MM`, not a fixed set of slots), so knowing "is anything due right now?" requires a process that keeps checking the clock. The original design used Celery Beat polling every 5 minutes, backed by a Celery worker and a Redis broker. That's three pieces that all need to run 24/7 — and most hosts (Railway, etc.) bill by uptime, not by work done, so an idle-but-always-on worker costs the same as a busy one.

**Solution:** Replaced Beat with an external free scheduler (cron-job.org) hitting a single `POST /api/cron/tick` endpoint every 5 minutes. The endpoint runs the same curate/dispatch check synchronously, in-process — no Redis broker, no separate worker. The backend itself deploys to a free tier (e.g. Render) that sleeps when idle; the cron ping doubles as the wake-up call, and since it fires more often than the platform's idle-sleep timeout, the service stays effectively warm anyway. Net effect: same reliability, $0 infra cost, one moving part instead of three.

**Key insight:** the existing ±5-minute match-window tolerance (see #2) already absorbed the cold-start delay from a sleeping instance, so no reliability was traded away for the cost savings.

---

## 2. Avoiding double-sends when curate/dispatch windows overlap

**Problem:** The scheduler tick runs every 5 minutes and matches slots within a ±5-minute tolerance window (to survive a slightly-late tick or a restart). That means two consecutive ticks can both land inside a slot's window — naively, that risks curating or emailing the same slot twice.

**Solution:** Idempotency at the data layer instead of the scheduling layer. Curation checks for an existing draft (`topic_id + slot + local_date`) before running, and a `DuplicateKeyError` on insert is treated as a benign race, not an error. Dispatch only sends drafts still in `delivery_status: "draft"` — once sent, the status flips, so a later tick that re-matches the same window finds nothing to do.

---

## 3. Topics created too close to their own delivery slot

**Problem:** Curation is meant to run 5 minutes ahead of dispatch so content is ready in time. But a topic created (or edited) only 1–2 minutes before its own slot can miss that lead-time window entirely — by the time the beat tick notices it, there's no draft yet and dispatch is about to fire.

**Solution:** `dispatch_slot` self-heals: if a topic due for the current slot has no draft when dispatch runs, it curates synchronously right there before sending, instead of silently skipping that delivery. Slightly slower for that one edge case, but nothing gets dropped.

---

## 4. Per-user timezones for arbitrary local delivery slots

**Problem:** Delivery times are stored and compared in local time (e.g. "08:00"), but the scheduler runs in UTC. Users can be in any timezone, and a slot like `00:10` can straddle midnight relative to the server's clock.

**Solution:** Convert `now` to each topic's configured local timezone before matching, and check delivery-date candidates across day −1/0/+1 so a midnight-straddling window still resolves to the correct calendar date for "already delivered today" bookkeeping.
