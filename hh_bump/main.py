from datetime import datetime, timezone
import requests

from hh_bump.config import Settings
from hh_bump.auth import get_stored_access_token, refresh_access_token
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramNotifier


def main():
    s = Settings()
    notifier = TelegramNotifier()

    # --- токен ---
    try:
        token = get_stored_access_token()

        if token:
            resp = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 401:
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

    # --- получаем резюме ---
    try:
        resumes = api.get_my_resumes()
    except Exception as e:
        notifier.send(f"❌ Ошибка получения резюме: {e}")
        return

    if not resumes:
        notifier.send("❌ Нет резюме для поднятия")
        return

    resume_ids = list(resumes.keys())
    n = len(resume_ids)

    # 👇 ВАЖНО: вращение, как раньше
    start_index = datetime.now(timezone.utc).hour % n

    for shift in range(n):
        idx = (start_index + shift) % n
        resume_id = resume_ids[idx]
        title = resumes[resume_id]

        try:
            api.publish_resume(resume_id)
            msg = f"✅ Резюме поднято ({idx + 1}/{n}): {title}"
            print(msg)
            notifier.send(msg)
            return

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print(f"⏳ cooldown: {title}")
                continue

            notifier.send(f"❌ Ошибка при поднятии {title}: {e}")
            return

    notifier.send("⚠️ Все резюме сейчас на cooldown")


if __name__ == "__main__":
    main()

