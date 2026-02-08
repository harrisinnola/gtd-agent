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

Return ONLY a valid JSON **array** of objects. Each object has these keys:

intent: one of ["next_action","waiting_for","someday","project","reference","inbox"]
title: short, clean action description (strip dates/filler words, keep names and verbs)
notes: optional extra context (may be empty string)
follow_up: YYYY-MM-DD or null

A message may contain one or many tasks. Split them into separate objects.
If the message contains only one task, still return a one-element array.

Rules:
- If a follow-up date is given or implied → waiting_for. Always set follow_up for waiting_for.
- If no date is given or implied → next_action (follow_up is null).
- If the user is waiting on someone else or delegated → waiting_for (default follow_up to {default_follow_up} if no date mentioned).
- If the user must personally do something and no date is mentioned → next_action.
- If a date IS mentioned for something the user must do → waiting_for with that date as follow_up.
- If it's a multi-step effort → project.
- If it's just capture with no clear action → inbox.
- If it's an idea with no commitment → someday.
- If it's a question, info, or reference material → reference.
- Resolve relative dates ("tomorrow", "next Monday", "in 3 days") to concrete YYYY-MM-DD using today's date.
No markdown. No commentary. JSON only.
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences GPT occasionally wraps around JSON."""
    m = _FENCE_RE.match(raw.strip())
    return m.group(1).strip() if m else raw.strip()


def _system_prompt() -> str:
    from datetime import timedelta
    today = date.today()
    default_follow_up = (today + timedelta(days=7)).isoformat()
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=today.isoformat(),
        weekday=today.strftime("%A"),
        default_follow_up=default_follow_up,
    )


def triage(text: str) -> list[dict]:
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
    parsed = json.loads(cleaned)
    # Normalize: always return a list
    if isinstance(parsed, dict):
        return [parsed]
    return parsed
