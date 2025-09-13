from datetime import datetime, timedelta, timezone

import requests

from .config import Settings
from .auth import (
    get_stored_access_token,
    refresh_access_token,
    store_access_token,
    load_state,
    save_state,
)
from .api import HHApi


def main():
    s = Settings()
    state = load_state()

    # защита от слишком частых запусков
    last_run_iso = state.get("last_success_utc")
    if last_run_iso and s.min_interval_minutes > 0:
        try:
            last_dt = datetime.fromisoformat(
                last_run_iso.replace("Z", "+00:00")
                )
            if datetime.now(timezone.utc) - last_dt < timedelta(
                minutes=s.min_interval_minutes):
                print("Skip: min_interval_minutes guard")
                return 0
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
                s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
            )

        api = HHApi(s.api_base, token)

        # проверка: жив ли токен (GET /me)
        try:
            resp = requests.get(f"{s.api_base}/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if resp.status_code == 401:
                print("access_token истёк — обновляем через refresh_token")
                token = refresh_access_token(
                    s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
                )
                api = HHApi(s.api_base, token)
        except Exception:
            pass

        # 2) список резюме
        all_ids = s.resume_ids or api.get_my_resume_ids()
        if not all_ids:
            raise RuntimeError(
                "У вас нет опубликованных резюме для обновления."
                )

        # 3) карусель: выбираем следующее резюме
        last_index = state.get("last_index", -1)
        next_index = (last_index + 1) % len(all_ids)
        resume_id = all_ids[next_index]

        # 4) поднимаем резюме
        api.publish_resume(resume_id)

        # 5) сохраняем состояние
        state["last_index"] = next_index
        state["last_success_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        state["last_id"] = resume_id
        save_state(state)

        print("OK (bumped):", resume_id)
        return 0

    except Exception as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
