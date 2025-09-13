# hh_bump/main.py
import json
from datetime import datetime, timedelta, timezone

from .config import Settings
from .auth import refresh_access_token
from .api import HHApi


def _load_state(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _save_state(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    s = Settings()
    state = _load_state(s.state_path)

    # Мягкая защита от слишком частого запуска
    last_run_iso = state.get("last_success_utc")
    if last_run_iso and s.min_interval_minutes > 0:
        try:
            last_dt = datetime.fromisoformat(
                last_run_iso.replace("Z", "+00:00")
                )
            if datetime.now(timezone.utc) - last_dt < timedelta(
                minutes=s.min_interval_minutes
            ):
                print("Skip: min_interval_minutes guard")
                return 0
        except Exception:
            pass

    try:
        # 1) access_token через refresh_token
        access = refresh_access_token(
            s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
        )

        # 2) API клиент
        api = HHApi(s.api_base, access)

        # 3) Список резюме: из config.ini или все мои
        all_ids = s.resume_ids or api.get_my_resume_ids()
        if not all_ids:
            raise RuntimeError(
                "У вас нет опубликованных резюме для обновления")

        # 4) Карусель: следующее резюме по кругу
        last_index = state.get("last_index", -1)
        next_index = (last_index + 1) % len(all_ids)
        resume_id = all_ids[next_index]

        # 5) Поднять одно резюме
        api.publish_resume(resume_id)

        # 6) Сохранить состояние
        state["last_index"] = next_index
        state["last_success_utc"] = datetime.now(
            timezone.utc).isoformat().replace("+00:00", "Z")
        state["last_id"] = resume_id
        _save_state(s.state_path, state)

        print("OK (bumped):", resume_id)
        return 0

    except Exception as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
