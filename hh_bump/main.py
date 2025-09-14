from datetime import datetime
from datetime import timezone
from datetime import timedelta

import requests

from .config import Settings
from .auth import (
    get_stored_access_token,
    refresh_access_token,
)
from .api import HHApi


def main():
    s = Settings()

    # защита от слишком частых запусков
    last_run_iso = None
    if s.min_interval_minutes > 0:
        try:
            # можно хранить это в будущем, если понадобится
            pass
        except Exception:
            pass

    try:
        # 1) пробуем использовать сохранённый access_token
        token = get_stored_access_token()

        if not token:
            print(
                "Нет сохранённого access_token — пробуем обновить через refresh_token"
                )
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token
            )

        api = HHApi(s.api_base, token)

        # проверка: жив ли токен (GET /me)
        try:
            resp = requests.get(f"{s.api_base}/me",
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=15)
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
            raise RuntimeError(
                "У вас нет опубликованных резюме для обновления.")

        # 3) выбираем резюме по формуле: час % количество_резюме
        utc_now = datetime.now(timezone.utc)
        next_index = utc_now.hour % len(all_ids)
        resume_id = all_ids[next_index]

        # 4) поднимаем резюме
        api.publish_resume(resume_id)

        print("OK (bumped):", resume_id)
        return 0

    except Exception as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
