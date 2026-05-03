# telegram_bot.py — Telegram message sender
import urequests
import gc
from secrets import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from locks import net_lock

_SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def send_telegram_msg(text, max_len=2000):
    """Send a message to the authorized Telegram chat.
    Messages are capped at max_len chars for concise updates."""
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."

    res = None
    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        with net_lock:
            res = urequests.post(_SEND_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram: Send failed: {e}")
    finally:
        if res:
            res.close()
        gc.collect()
