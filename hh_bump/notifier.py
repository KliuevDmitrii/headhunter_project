import os
import requests
from pathlib import Path


class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TG_BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")

        if not self.token or not self.chat_id:
            raise RuntimeError("Не заданы TG_BOT_TOKEN или TG_CHAT_ID")

        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, text: str, file_path: Path | None = None):
        """
        Отправляет сообщение в Telegram.
        Если передан file_path — отправляет файл вместе с сообщением.
        """

        if file_path:
            self._send_document(text, file_path)
        else:
            self._send_message(text)

    def _send_message(self, text: str):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()

    def _send_document(self, caption: str, file_path: Path):
        url = f"{self.base_url}/sendDocument"

        with file_path.open("rb") as f:
            files = {
                "document": (file_path.name, f),
            }
            data = {
                "chat_id": self.chat_id,
                "caption": caption,
            }

            r = requests.post(url, data=data, files=files, timeout=60)
            r.raise_for_status()



