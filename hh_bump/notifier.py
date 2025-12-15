import os
import requests


class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TG_BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")

        if not self.token or not self.chat_id:
            raise RuntimeError("Не заданы TG_BOT_TOKEN или TG_CHAT_ID")

        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, text: str):
        """
        Отправка текстового сообщения
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }

        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()

    def send_file(self, caption: str, file_path: str):
        """
        Отправка файла с подписью
        """
        url = f"{self.base_url}/sendDocument"

        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {
                "chat_id": self.chat_id,
                "caption": caption,
            }

            r = requests.post(url, data=data, files=files, timeout=60)
            r.raise_for_status()


