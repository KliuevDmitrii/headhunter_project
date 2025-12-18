import requests
from pathlib import Path


class TelegramNotifier:
    def __init__(self):
        from hh_bump.config import Settings

        s = Settings()

        if not s.tg_bot_token or not s.tg_chat_id:
            raise RuntimeError("❌ TG_BOT_TOKEN или TG_CHAT_ID не заданы")

        self.token = s.tg_bot_token
        self.chat_id = s.tg_chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, text: str, file_path: Path | None = None):
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        r = requests.post(f"{self.api_url}/sendMessage", json=payload)
        r.raise_for_status()

        if file_path:
            with file_path.open("rb") as f:
                files = {"document": f}
                data = {"chat_id": self.chat_id}
                r = requests.post(
                    f"{self.api_url}/sendDocument",
                    data=data,
                    files=files,
                )
                r.raise_for_status()
