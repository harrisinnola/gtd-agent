import os
import json
import logging
import re
from openai import OpenAI

log = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You triage messages into a GTD system.
Return ONLY valid JSON with these keys:

intent: one of ["inbox","next_action","waiting_for","someday","project","reference"]
title: short, concrete string
notes: optional string (may be empty)
due: YYYY-MM-DD or null
follow_up: YYYY-MM-DD or null

Rules:
- If the user needs to wait on someone else: waiting_for (+ follow_up if implied).
- If the user must do something: next_action (+ due if implied).
- If it's just capture: inbox.
- If it's an idea with no commitment: someday.
- If it's a question or info request: reference.
- If no date is clear, use null.
No markdown. No commentary. JSON only.
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences GPT occasionally wraps around JSON."""
    m = _FENCE_RE.match(raw.strip())
    return m.group(1).strip() if m else raw.strip()


def triage(text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    content = resp.choices[0].message.content
    cleaned = _strip_fences(content)
    log.debug("LLM raw response: %s", content)
    return json.loads(cleaned)
