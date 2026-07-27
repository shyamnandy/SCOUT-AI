"""Newsletter output schemas."""

from pydantic import BaseModel
from datetime import datetime

# Pipeline states meaning "curated, but no email has gone out yet". Shared
# so the API and the worker agree on what counts as undelivered.
UNSENT_STATUSES = ("draft", "pending")

# How long a newsletter survives after it's sent. The worker deletes past
# this age and the API refuses to serve past it, so the two can't disagree
# about what History holds even if the scheduler stops ticking.
RETENTION_HOURS = 24


class ArticleSummary(BaseModel):
    title: str
    summary: str
    source_url: str
    source_name: str
    relevance_score: float = 0.0


class NewsletterListItem(BaseModel):
    """One row of History. No article bodies or rendered HTML — the list
    view only ever shows a title, a count, and a status chip, so shipping
    the full email markup (which can run several KB) per row for up to 50
    rows was pure wasted bandwidth and serialization time."""
    id: str
    topic_id: str
    topic_name: str
    title: str
    article_count: int
    delivered_at: datetime
    delivery_status: str


class NewsletterResponse(NewsletterListItem):
    """Full detail for a single newsletter, fetched on demand when the
    reader actually opens one."""
    articles: list[ArticleSummary]
    html_content: str
