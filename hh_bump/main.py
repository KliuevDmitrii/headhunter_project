from datetime import datetime, timezone
import requests

from hh_bump.config import Settings
from hh_bump.auth import (
    get_stored_access_token,
    refresh_access_token,
)
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramNotifier


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        # 1. Получаем токен (из state.json или окружения)
        token = get_stored_access_token()

        # 2. Проверяем токен через /me
        if token:
            resp = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 401:
                print("access_token истёк — обновляем через refresh_token")
                token = None

        # 3. Если токена нет или он истёк, обновляем
        if not token:
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token
            )

        # 4. Создаём API клиент
        api = HHApi(s.api_base, token)

    except Exception as e:
        msg = f"❌ Ошибка получения access_token: {e}"
        print(msg)
        notifier.send(msg)
        return 1

    # --- резюме ---
    try:
        all_resumes = api.get_my_resumes()
        all_ids = list(all_resumes.keys())

        if not all_ids:
            raise RuntimeError("У вас нет опубликованных резюме для обновления.")

        n = len(all_ids)
        utc_now = datetime.now(timezone.utc)
        start_index = utc_now.hour % n

        # 5. Пытаемся поднять резюме по кругу
        for shift in range(n):
            idx = (start_index + shift) % n
            resume_id = all_ids[idx]
            title = all_resumes[resume_id]

            try:
                api.publish_resume(resume_id)
                msg = f"✅ Резюме поднято ({idx+1}/{n}): {title}"
                print(msg)
                notifier.send(msg)
                return 0

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    msg = f"⚠️ Резюме «{title}» ещё нельзя поднимать (429)"
                    print(msg)
                    notifier.send(msg)
                    continue
                else:
                    raise

        # Все резюме на cooldown
        msg = "⚠️ Все резюме пока на cooldown, пропуск запуска."
        print(msg)
        notifier.send(msg)
        return 0

    except Exception as e:
        msg = f"❌ Ошибка: {e}"
        print(msg)
        notifier.send(msg)
        return 1


if __name__ == "__main__":
    main()



