import os
import requests


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TG_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TG_CHAT_ID")

    def send(self, message: str):
        if not self.token or not self.chat_id:
            print("⚠️ Telegram notifier is not configured, skipping message.")
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            r = requests.post(url, data=payload, timeout=10)
            r.raise_for_status()
            print("📨 Telegram notification sent.")
        except Exception as e:
            print("⚠️ Failed to send Telegram message:", e)
