import logging
import os
import time

import requests

from notion import create_page
from router import triage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("poller")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = "/data/offset.txt"

TYPE_MAP = {
    "inbox": "Inbox",
    "next_action": "Next Action",
    "nextaction": "Next Action",
    "waiting_for": "Waiting For",
    "waitingfor": "Waiting For",
    "someday": "Someday",
    "project": "Project",
    "reference": "Reference",
}


def send_message(chat_id: int, text: str):
    requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )


def load_offset() -> int:
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def save_offset(offset: int):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def normalize_intent(v: str | None) -> str:
    if not v:
        return "inbox"
    v = v.strip().lower()
    v = v.replace("-", "_").replace(" ", "_")
    return v


def save_item(item: dict, raw_text: str):
    intent = normalize_intent(item.get("intent"))
    notion_type = TYPE_MAP.get(intent, "Inbox")

    title = (item.get("title") or "").strip() or raw_text
    notes = (item.get("notes") or "").strip()

    props = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Type": {"select": {"name": notion_type}},
        "Status": {"select": {"name": "Active"}},
        "Source": {"rich_text": [{"text": {"content": "Telegram"}}]},
        "Notes": {"rich_text": [{"text": {"content": notes}}]},
    }

    due = item.get("due")
    if isinstance(due, str) and due.strip():
        props["Due"] = {"date": {"start": due.strip()}}

    follow = item.get("follow_up")
    if isinstance(follow, str) and follow.strip():
        props["Follow-up"] = {"date": {"start": follow.strip()}}

    log.info("Saving → Type=%s  Title=%s", notion_type, title)
    create_page(props)


def _normalize_item(item: dict, fallback_text: str) -> dict:
    item.setdefault("intent", "inbox")
    item.setdefault("title", fallback_text)
    item.setdefault("notes", "")
    item.setdefault("due", None)
    item.setdefault("follow_up", None)
    return item


def safe_triage(text: str) -> list[dict]:
    try:
        items = triage(text)
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or not items:
            log.warning("LLM returned unexpected type: %r — falling back to inbox", items)
            return [{"intent": "inbox", "title": text, "notes": ""}]
        return [_normalize_item(it, text) for it in items if isinstance(it, dict)]
    except Exception:
        log.exception("Triage failed for text: %s", text[:200])
        return [{"intent": "inbox", "title": text, "notes": ""}]


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in container env")

    offset = load_offset()
    log.info("Poller started (offset=%d)", offset)

    while True:
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=35,
            )
            r.raise_for_status()
            payload = r.json()

            for upd in payload.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                text = (msg.get("text") or "").strip()

                if not chat_id or not text:
                    continue

                if text == "/start":
                    send_message(chat_id, "Ready. Send me anything to capture/triage into Notion.")
                    continue

                items = safe_triage(text)
                saved = []

                for item in items:
                    try:
                        save_item(item, text)
                        label = TYPE_MAP.get(normalize_intent(item.get("intent")), "Inbox")
                        saved.append(f"{label}: {item.get('title', text)}")
                    except Exception:
                        log.exception("Notion save failed for item: %r", item)
                        saved.append(f"[ERROR] {item.get('title', text)}")

                reply = "\n".join(f"Saved \u2192 {s}" for s in saved)
                send_message(chat_id, reply or "Error saving to Notion. Check poller logs.")

            save_offset(offset)

        except Exception:
            log.exception("Poll loop error")
            time.sleep(2)


if __name__ == "__main__":
    main()
