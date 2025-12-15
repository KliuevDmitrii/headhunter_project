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
                timeout=15,
            )
            if r.status_code == 401:
                token = None

        if not token:
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token
            )

        api = HHApi(s.api_base, token)

    except Exception as e:
        notifier.send(f"❌ Ошибка токена: {e}")
        return

    resume_ids = s.resume_ids
    n = len(resume_ids)

    if n == 0:
        notifier.send("❌ Нет resume_ids в config.ini")
        return

    # ⚙️ выбор резюме по времени (round-robin)
    hour = datetime.now(timezone.utc).hour
    start_index = hour % n

    for shift in range(n):
        idx = (start_index + shift) % n
        resume_id = resume_ids[idx]

        try:
            api.publish_resume(resume_id)
            msg = f"✅ Резюме поднято ({idx+1}/{n})"
            print(msg)
            notifier.send(msg)
            return

        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 429:
                    print(f"⏱️ cooldown для resume {resume_id}")
                    continue
                if e.response.status_code == 403:
                    print(f"🚫 недоступно resume {resume_id}")
                    continue
            raise

    notifier.send("⚠️ Все резюме пока на cooldown или недоступны")


if __name__ == "__main__":
    main()
