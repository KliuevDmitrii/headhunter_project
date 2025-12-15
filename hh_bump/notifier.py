import os
import requests
from pathlib import Path

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TG_BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")

    def send(self, text: str):
        if not self.token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        requests.post(
            url,
            json={"chat_id": self.chat_id, "text": text},
            timeout=20,
        )

    def send_file(self, file_path: str, caption: str | None = None):
        if not self.token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": self.chat_id}
            if caption:
                data["caption"] = caption

            requests.post(url, files=files, data=data, timeout=60)

