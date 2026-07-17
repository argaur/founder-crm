import os
import json
import base64
import time
import asyncio
import inspect
import functools
from typing import Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Single provider: OpenAI for both reasoning/extraction (gpt-4o-mini — cheap,
# supports vision + JSON mode) and audio transcription (Whisper). Previously
# split across Anthropic (Claude Haiku) + OpenAI (Whisper) — consolidated to
# one account/one key on 2026-07-17 (Claude has no audio-input endpoint, so
# full consolidation means picking the provider that covers both; OpenAI does).
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constants
CHAT_MODEL = "gpt-4o-mini"
WHISPER_MODEL = "whisper-1"

STAGES = "Inquiry, Qualified, Site Visit, Proposal, Negotiation, Closed-Won, Closed-Lost"

_COWORKING_CONTEXT = """Deals are about workspace requirements: seats, dedicated desks, private cabins, day passes, and managed offices. Interpret coworking vocabulary — seat count, price per seat, lock-in period, security deposit, fit-out, site visit, move-in date — as deal signals."""


def _extraction_schema(summary_desc: str) -> str:
    return f"""Return JSON with EXACTLY these fields:
{{
  "contact_name": "full name of the person being discussed (string or null)",
  "company": "company or organisation name (string or null)",
  "role": "their job title or role (string or null)",
  "stage": "one of: {STAGES}. Use 'unknown' only if the stage genuinely cannot be inferred.",
  "summary": "{summary_desc}",
  "next_action": "suggested next step (string or null)",
  "budget_signal": "any pricing or budget info mentioned (string or null)",
  "seat_count": "number of seats/desks required (integer or null)",
  "city": "city where the workspace is needed (string or null)",
  "space_type": "one of: Dedicated Desk, Private Cabin, Managed Office, Day Pass (or null if not stated)",
  "budget_per_seat": "monthly price per seat if mentioned (number or null)",
  "move_in_date": "desired move-in date, exact or relative e.g. 'next month' (string or null)"
}}"""


def retry_api_call(func):
    """Decorator for 2 retries with 1s delay. Handles both sync and async functions."""
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(3):  # Initial try + 2 retries
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < 2:
                        await asyncio.sleep(1)
            raise last_exception
        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(3):  # Initial try + 2 retries
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < 2:
                    time.sleep(1)
        raise last_exception
    return wrapper


@retry_api_call
async def transcribe_voice(file_path: str) -> str:
    """Uses OpenAI Whisper to transcribe audio files."""
    with open(file_path, "rb") as audio_file:
        transcript = await openai_client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
        )
    return transcript.text


async def _openai_json_extract(prompt: str, system_prompt: str, image_data: Optional[Dict] = None) -> Dict:
    """Internal helper to ensure the model returns valid JSON."""
    content = [{"type": "text", "text": prompt}]
    if image_data:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{image_data['mime_type']};base64,{image_data['base64']}"},
        })

    response = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        max_tokens=1000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + "\nOutput ONLY valid JSON."},
            {"role": "user", "content": content},
        ],
    )

    try:
        text = response.choices[0].message.content.strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError, AttributeError):
        return {"contact_name": None, "error": "Failed to parse AI response"}


@retry_api_call
async def extract_from_text(text: str) -> Dict:
    """Extracts deal context from forwarded WhatsApp text."""
    system_prompt = f"""You are a sales operations assistant for the B2B sales team of an Indian coworking space aggregator.
Extract deal info from forwarded WhatsApp chats. {_COWORKING_CONTEXT}
If confidence is low on contact_name, set it to null.
{_extraction_schema("one sentence summary of what happened in this interaction")}"""

    prompt = f"Extract structured data from this chat log:\n\n{text}"
    return await _openai_json_extract(prompt, system_prompt)


@retry_api_call
async def extract_from_voice(transcript: str) -> Dict:
    """Extracts deal context from voice note transcripts (handles Hinglish/informal)."""
    system_prompt = f"""You are a sales assistant for the B2B sales team of an Indian coworking space aggregator. The input is a voice note transcript (may include Hinglish, filler words, or informal speech).
{_COWORKING_CONTEXT}
Listen for seat counts (e.g. "50 seats chahiye", "200 log shift ho rahe hain"), cities, cabin/desk/day-pass mentions, price per seat, lock-in, security deposit, fit-out, and site-visit plans.
Extract the deal context.
{_extraction_schema("one sentence summary of what happened in this interaction")}"""

    prompt = f"Extract deal data from this voice note transcript:\n\n{transcript}"
    return await _openai_json_extract(prompt, system_prompt)


@retry_api_call
async def extract_from_image(image_bytes: bytes, mime_type: str) -> Dict:
    """Uses vision to extract deal info from screenshots/business cards."""
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    system_prompt = f"""You are a sales CRM assistant for the B2B sales team of an Indian coworking space aggregator.
Extract contact and deal info from this image (LinkedIn profile, WhatsApp contact, business card, workspace requirement brief, etc).
{_COWORKING_CONTEXT}
{_extraction_schema("one sentence describing what you see in the image")}"""
    prompt = "Extract the contact and deal information from this image and return the JSON."

    return await _openai_json_extract(
        prompt,
        system_prompt,
        image_data={"base64": base64_image, "mime_type": mime_type},
    )


@retry_api_call
async def classify_intent(text: str) -> str:
    """Detects if a sales rep wants to 'capture' info or 'recall' for a meeting."""
    prompt = f"Classify this coworking sales rep's intent as either 'capture' (logging a lead or deal update) or 'recall' (asking for a summary/meeting prep). Text: {text}"

    response = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    res_text = response.choices[0].message.content.lower()
    return "recall" if "recall" in res_text else "capture"


@retry_api_call
async def evaluate_note_quality(note_text: str) -> Dict:
    """Checks if a note is useful or needs a follow-up question."""
    system_prompt = "Check if this coworking sales note is complete (has topic, outcome, or next step — e.g. seat requirement, site-visit outcome, proposal follow-up). If not, provide ONE specific follow-up question. Respond with JSON: {\"is_complete\": bool, \"follow_up_question\": str|null}"
    prompt = f"Evaluate this note: {note_text}"

    return await _openai_json_extract(prompt, system_prompt)


@retry_api_call
async def answer_pipeline_query(question: str, pipeline_context: str) -> str:
    """Natural language Q&A over the current pipeline status."""
    prompt = f"""
    Context (Current coworking sales pipeline):
    {pipeline_context}

    Question: {question}

    Answer concisely in plain text. If the question is too vague, return exactly ONE clarifying question.
    """

    response = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


@retry_api_call
async def generate_context_brief(contact_record: Dict, interactions: List[str]) -> str:
    """Generates a pre-call briefing string."""
    history = "\n".join(interactions[-5:])  # Last 5 interactions
    prompt = f"""
    Contact: {contact_record.get('contact_name')}
    Company: {contact_record.get('company')}
    Stage: {contact_record.get('stage')}
    Heat Score: {contact_record.get('heat_score')}
    Budget: {contact_record.get('budget_signal')}

    Recent History:
    {history}

    Generate a concise pre-call brief for the coworking sales rep.
    Include: Current status, last touchpoint summary, and 2 suggested talking points.
    """

    response = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
