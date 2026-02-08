import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def send_message(chat_id: int, text: str):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()
    msg = data.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if not chat_id:
        return {"ok": True}

    send_message(chat_id, f"got it: {text}")
    return {"ok": True}
