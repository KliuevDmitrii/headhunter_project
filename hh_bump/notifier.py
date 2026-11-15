from pathlib import Path

import requests


class TelegramError(RuntimeError):
    """A delivery error safe to include in logs (without the bot token)."""


class TelegramNotifier:
    # Separate connect/read limits also cover report uploads.
    timeout = (10, 60)

    def __init__(self):
        from hh_bump.config import Settings

        s = Settings()

        self.token = (s.tg_bot_token or "").strip()
        self.chat_id = (s.tg_chat_id or "").strip()
        missing = [
            name
            for name, value in (
                ("TG_BOT_TOKEN", self.token),
                ("TG_CHAT_ID", self.chat_id),
            )
            if not value
        ]
        if missing:
            raise TelegramError(
                "Не заданы переменные окружения Telegram: " + ", ".join(missing)
            )
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def _post(self, method: str, **kwargs):
        # Retrying a timed-out POST can deliver the same message twice.
        try:
            response = requests.post(
                f"{self.api_url}/{method}", timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            # Preserve the failure category, never the exception text: requests
            # includes the complete URL (and bot token) in transport errors.
            if isinstance(exc, requests.ConnectTimeout):
                description = (
                    "соединение не установлено: истекло время подключения "
                    f"(лимит {self.timeout[0]} с); проверьте DNS и HTTPS-доступ "
                    "к api.telegram.org с машины, запускающей скрипт"
                )
            elif isinstance(exc, requests.ReadTimeout):
                description = (
                    f"ответ не получен в течение {self.timeout[1]} с; "
                    "результат доставки неизвестен; проверьте доступ к "
                    "api.telegram.org с машины, запускающей скрипт"
                )
            elif isinstance(exc, requests.Timeout):
                description = (
                    "превышено время ожидания; результат доставки неизвестен; "
                    "проверьте доступ к api.telegram.org"
                )
            elif isinstance(exc, requests.exceptions.SSLError):
                description = (
                    "ошибка TLS; проверьте сертификаты и HTTPS-доступ "
                    "к api.telegram.org"
                )
            elif isinstance(exc, requests.exceptions.ProxyError):
                description = (
                    "ошибка прокси; проверьте настройки прокси и разрешение "
                    "доступа к api.telegram.org"
                )
            else:
                description = "ошибка соединения; проверьте доступ к api.telegram.org"
            raise TelegramError(
                f"Telegram {method}: {type(exc).__name__}: {description}"
            ) from None

        try:
            result = response.json()
        except ValueError:
            result = None
        if (
            200 <= response.status_code < 300
            and isinstance(result, dict)
            and result.get("ok") is True
        ):
            return result

        description = "некорректный ответ API"
        if isinstance(result, dict):
            description = str(result.get("description") or description)
            parameters = result.get("parameters")
            if isinstance(parameters, dict):
                retry_after = parameters.get("retry_after")
                if isinstance(retry_after, int):
                    description += f"; повторите через {retry_after} с"
        for value in (self.token, self.chat_id):
            description = description.replace(value, "[REDACTED]")
        description = description[:500]
        raise TelegramError(
            f"Telegram {method}: HTTP {response.status_code}: {description}"
        )

    def _send_message(self, text: str):
        self._post(
            "sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )

    def send(self, text: str, file_path: Path | None = None):
        if file_path is None:
            self._send_message(text)
            return

        # Open the report before sending anything, so a missing file cannot
        # produce a success-looking notification without its attachment.
        with Path(file_path).open("rb") as report:
            data = {"chat_id": self.chat_id}
            # Counting the raw HTML as UTF-16 is conservative: Telegram's
            # caption limit applies after parsing entities.
            if len(text.encode("utf-16-le")) // 2 <= 1024:
                data.update(caption=text, parse_mode="HTML")
            else:
                self._send_message(text)
            self._post(
                "sendDocument",
                data=data,
                files={"document": report},
            )
