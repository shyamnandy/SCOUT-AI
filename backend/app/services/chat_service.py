"""Conversational onboarding service using LangChain + Groq (or OpenAI fallback)."""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.config import get_settings, get_llm
from app.schemas.chat import ExtractedTopic
from pydantic import BaseModel, Field

settings = get_settings()

ONBOARDING_SYSTEM_PROMPT = """You are ScoutAI's onboarding assistant helping the user define ONE specific news topic they want to follow.

YOUR GOAL: Understand exactly what kind of news the user wants for a SINGLE topic, then confirm it.

CONVERSATION RULES:
1. Ask what ONE topic or area they want to follow.
2. Ask 1-2 clarifying questions to get specifics:
   - For tech: "Are you focused on AI research, AI products, or software dev?"
   - For sports: "Which sport? Any specific team or league?"
   - For finance: "Stocks, crypto, personal finance, or macro economics?"
   - For world news: "Any specific region or global events?"
3. Keep responses SHORT (2-3 sentences max).
4. Once you understand the topic well, summarize it clearly, ask "Does this look right?", and end your message with the exact marker [AWAITING_CONFIRMATION]. The user confirms via a button in the UI — do not wait for a typed "yes".
5. If the user replies after that asking to change something, drop the marker and keep clarifying. Only include [AWAITING_CONFIRMATION] again once you have an updated, accurate summary ready.

TOPIC CATEGORIES: technology, world_news, finance, sports, entertainment, science

IMPORTANT: Focus on ONE topic only. Do NOT ask about multiple topics in one conversation."""


class TopicExtraction(BaseModel):
    """Structured output for extracting a single topic from conversation."""
    topics: list[ExtractedTopic] = Field(
        description="List with exactly ONE extracted topic"
    )


def get_chat_llm(groq_api_key: str | None = None):
    """Get the configured LLM instance (Groq if GROQ_API_KEY is set, else OpenAI).

    `groq_api_key` lets a caller use a user's own Groq key; falls back to the
    shared app-level key when omitted.
    """
    return get_llm(temperature=0.7, groq_api_key=groq_api_key)


async def chat_onboarding(
    messages_history: list[dict], user_message: str, groq_api_key: str | None = None
) -> dict:
    """
    Process a user message in the onboarding conversation.
    Returns the AI reply and any extracted topic when confirmed.
    """
    llm = get_chat_llm(groq_api_key)

    lc_messages = [SystemMessage(content=ONBOARDING_SYSTEM_PROMPT)]

    for msg in messages_history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))

    lc_messages.append(HumanMessage(content=user_message))

    response = await llm.ainvoke(lc_messages)
    reply = response.content

    awaiting_confirmation = "[AWAITING_CONFIRMATION]" in reply
    if awaiting_confirmation:
        reply = reply.replace("[AWAITING_CONFIRMATION]", "").strip()

    return {
        "reply": reply,
        "awaiting_confirmation": awaiting_confirmation,
    }


async def extract_single_topic(
    messages: list[dict], groq_api_key: str | None = None
) -> list[ExtractedTopic]:
    """
    Use structured output to extract the single confirmed topic from the conversation.
    """
    llm = get_chat_llm(groq_api_key)
    # Groq's llama models reject the `json_schema` response format that
    # with_structured_output uses by default, so pin it to JSON mode.
    structured_llm = llm.with_structured_output(TopicExtraction, method="json_mode")

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in messages
    )

    extraction_prompt = f"""Analyze this conversation and extract exactly ONE news topic the user confirmed.

Respond with a JSON object of this exact shape:
{{"topics": [{{"name": str, "keywords": [str], "category": str, "description": str, "suggested_lifecycle": str}}]}}

Field rules:
- name: A clear, concise topic name (e.g., "AI Product Launches", "Premier League Football")
- keywords: 4-6 specific search keywords that would find relevant news articles
- category: One of: technology, world_news, finance, sports, entertainment, science
- description: A 1-sentence summary of what the user SPECIFICALLY wants from this topic — carry over
  any nuance from the conversation (their angle, context, or goal — e.g. "as a CSE student looking
  for practical tools", "match results and player performance, not transfer rumors"), not just a
  restatement of the topic name. This is used later to steer what gets searched and selected, so
  keep whatever specifics the user gave beyond the bare keywords.
- suggested_lifecycle: "perpetual" for ongoing interests, "ephemeral" for event-based topics

CONVERSATION:
{conversation_text}

Return JSON with the ONE confirmed topic."""

    result = await structured_llm.ainvoke(extraction_prompt)
    return result.topics[:1] if result else []
