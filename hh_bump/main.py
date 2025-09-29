from datetime import datetime, timezone
import requests
import os

from hh_bump.config import Settings
from hh_bump.auth import (
    get_stored_access_token,
    refresh_access_token,
    store_access_token,
    save_state,
)
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramNotifier


def get_valid_token(s: Settings, notifier: TelegramNotifier) -> str | None:
    """
    Возвращает валидный access_token.
    При необходимости обновляет его через refresh_token.
    """
    token = get_stored_access_token()

    # Проверка /me
    if token:
        try:
            resp = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 401:
                print("⚠️ access_token истёк (401) — обновляем...")
                token = None
            elif resp.status_code == 403:
                print("⚠️ access_token запрещён (403) — обновляем...")
                token = None
        except Exception as e:
            print(f"⚠️ Ошибка при проверке access_token: {e}")
            token = None

    # Обновление токена
    if not token:
        try:
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token
            )
            print("✅ Новый access_token получен")
        except Exception as e:
            msg = f"❌ Ошибка обновления access_token: {e}"
            print(msg)
            notifier.send(msg)
            return None

    return token


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        token = get_valid_token(s, notifier)
        if not token:
            return

        api = HHApi(s.api_base, token)

        # Получение резюме
        resumes = api.get_my_resumes()
        if not resumes:
            msg = "❌ У пользователя нет резюме."
            print(msg)
            notifier.send(msg)
            return

        # --- Поднятие одного из резюме ---
        all_ids = list(resumes.keys())
        n = len(all_ids)
        utc_now = datetime.now(timezone.utc)
        start_index = utc_now.hour % n

        for shift in range(n):
            idx = (start_index + shift) % n
            resume_id = all_ids[idx]
            title = resumes[resume_id]

            try:
                api.publish_resume(resume_id)
                msg = f"✅ Резюме поднято ({idx + 1}/{n}): {title}"
                print(msg)
                notifier.send(msg)
                return
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    msg = f"⚠️ Резюме «{title}» ещё нельзя поднимать (429)"
                    print(msg)
                    continue
                raise

        msg = "⚠️ Все резюме пока на cooldown, пропуск запуска."
        print(msg)
        notifier.send(msg)

    except Exception as e:
        msg = f"❌ Ошибка: {e}"
        print(msg)
        notifier.send(msg)


if __name__ == "__main__":
    main()




