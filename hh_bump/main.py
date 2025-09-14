from datetime import datetime, timezone
import requests

from .config import Settings
from .auth import (
    get_stored_access_token,
    refresh_access_token,
)
from .api import HHApi
from .notifier import TelegramNotifier


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        # 1) пробуем использовать сохранённый access_token
        token = get_stored_access_token()
        if not token:
            print("Нет сохранённого access_token — пробуем обновить через refresh_token")
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token
            )

        api = HHApi(s.api_base, token)

        # проверка: жив ли токен (GET /me)
        try:
            resp = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 401:
                print("access_token истёк — обновляем через refresh_token")
                token = refresh_access_token(
                    s.oauth_token_url,
                    s.client_id,
                    s.client_secret,
                    s.refresh_token
                )
                api = HHApi(s.api_base, token)
        except Exception:
            pass

        # 2) список резюме
        all_ids = s.resume_ids or api.get_my_resume_ids()
        if not all_ids:
            raise RuntimeError("У вас нет опубликованных резюме для обновления.")

        n = len(all_ids)
        utc_now = datetime.now(timezone.utc)
        start_index = utc_now.hour % n

        # 3) пробуем по очереди резюме, пока не найдём доступное
        for shift in range(n):
            idx = (start_index + shift) % n
            resume_id = all_ids[idx]
            try:
                api.publish_resume(resume_id)
                msg = f"✅ Резюме поднято ({idx+1}/{n}): {resume_id}"
                print(msg)
                notifier.send(msg)
                return 0
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    msg = f"⚠️ Резюме {resume_id} ещё нельзя поднимать (429)"
                    print(msg)
                    notifier.send(msg)
                    continue
                raise

        # если все резюме ещё на cooldown
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
    raise SystemExit(main())
