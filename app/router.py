import os
import json
import logging
import re
from datetime import date
from openai import OpenAI

log = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT_TEMPLATE = """You triage messages into a GTD system.
Today is {today} ({weekday}).

Return ONLY valid JSON with these keys:

intent: one of ["inbox","next_action","waiting_for","someday","project","reference"]
title: short, clean action description (strip dates/filler words, keep names and verbs)
notes: optional extra context (may be empty string)
due: YYYY-MM-DD or null
follow_up: YYYY-MM-DD or null

Rules:
- If the user must personally do something → next_action (set due if a date is mentioned or implied).
- If the user is waiting on someone else or delegated → waiting_for (set follow_up if a date is mentioned or implied).
- If it involves coordinating with someone but the user is doing the work → next_action, not waiting_for.
- If it's a multi-step effort → project.
- If it's just capture with no clear action → inbox.
- If it's an idea with no commitment → someday.
- If it's a question, info, or reference material → reference.
- Resolve relative dates ("tomorrow", "next Monday", "in 3 days") to concrete YYYY-MM-DD using today's date.
- If no date is mentioned or implied, use null.
No markdown. No commentary. JSON only.
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences GPT occasionally wraps around JSON."""
    m = _FENCE_RE.match(raw.strip())
    return m.group(1).strip() if m else raw.strip()


def _system_prompt() -> str:
    today = date.today()
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=today.isoformat(),
        weekday=today.strftime("%A"),
    )


def triage(text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": text},
        ],
    )
    content = resp.choices[0].message.content
    cleaned = _strip_fences(content)
    log.debug("LLM raw response: %s", content)
    return json.loads(cleaned)
