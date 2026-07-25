"""Newsletter output schemas."""

from pydantic import BaseModel
from datetime import datetime


class ArticleSummary(BaseModel):
    title: str
    summary: str
    source_url: str
    source_name: str
    relevance_score: float = 0.0


class NewsletterOutput(BaseModel):
    title: str
    greeting: str
    articles: list[ArticleSummary]
    closing: str


class NewsletterResponse(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    title: str
    articles: list[ArticleSummary]
    html_content: str
    delivered_at: datetime
    delivery_status: str
