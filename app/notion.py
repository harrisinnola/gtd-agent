import json
import logging
import os
import requests

log = logging.getLogger(__name__)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def create_page(properties: dict):
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise RuntimeError("Missing NOTION_API_KEY or NOTION_DATABASE_ID")

    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    log.debug("Notion payload: %s", json.dumps(payload, indent=2))

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )

    if not r.ok:
        body = r.text
        log.error(
            "Notion API %s — %s\nPayload properties: %s\nResponse body: %s",
            r.status_code,
            r.reason,
            json.dumps(properties, indent=2),
            body,
        )
        r.raise_for_status()

    return r.json()
