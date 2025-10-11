import os
import requests
from pathlib import Path


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TG_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TG_CHAT_ID")

    def send(self, message: str):
        """
        Отправка текстового сообщения в Telegram.
        """
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

    def send_file(self, file_path: str | Path, caption: str = "📎 Отчёт"):
        """
        Отправка файла в Telegram как документа.
        """
        if not self.token or not self.chat_id:
            print("⚠️ Telegram notifier is not configured, skipping file send.")
            return

        file_path = Path(file_path)
        if not file_path.exists():
            print(f"⚠️ File not found: {file_path}")
            return

        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": self.chat_id, "caption": caption}
                r = requests.post(url, data=data, files=files, timeout=30)
                r.raise_for_status()
                print(f"📤 File sent to Telegram: {file_path.name}")
        except Exception as e:
            print(f"⚠️ Failed to send file to Telegram: {e}")
