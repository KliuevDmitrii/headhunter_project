# hh_bump/main.py
from datetime import datetime, timezone
import requests

from hh_bump.config import Settings
from hh_bump.auth import get_stored_access_token, refresh_access_token
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramNotifier


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        token = get_stored_access_token()

        if token:
            r = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if r.status_code == 401:
                token = None

        if not token:
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token,
            )

        api = HHApi(s.api_base, token)

    except Exception as e:
        notifier.send(f"❌ Ошибка получения токена: {e}")
        return 1

    resume_ids = s.resume_ids
    n = len(resume_ids)
    utc_hour = datetime.now(timezone.utc).hour
    start_index = utc_hour % n

    for shift in range(n):
        idx = (start_index + shift) % n
        resume_id = resume_ids[idx]

        try:
            api.publish_resume(resume_id)
            notifier.send(f"✅ Резюме поднято: {resume_id}")
            return 0

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                continue  # cooldown
            if e.response is not None and e.response.status_code == 403:
                continue  # это резюме сейчас нельзя поднимать
            raise

    notifier.send("⚠️ Все резюме на cooldown или недоступны")
    return 0


if __name__ == "__main__":
    main()