import csv
import requests
from pathlib import Path

from hh_bump.api import HHApi
from hh_bump.config import Settings
from hh_bump.auth import get_stored_access_token, refresh_access_token
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
                s.refresh_token,
            )

        api = HHApi(s.api_base, token)

    except Exception as e:
        notifier.send(f"❌ Ошибка авторизации: {e}")
        return

    # --- файл ---
    output_file = Path(s.vacancy_output_file)
    output_file.unlink(missing_ok=True)  # перезаписываем каждый запуск

    rows = []
    searches_done = 0

    for text in s.apply_search_texts:
        for area in s.apply_areas:
            for page in range(s.apply_max_pages):
                if searches_done >= s.max_searches_per_run:
                    break

                try:
                    vacancies = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.apply_per_page,
                        page=page,
                    )
                    searches_done += 1
                except Exception:
                    continue

                if not vacancies:
                    break

                for v in vacancies:
                    rows.append({
                        "vacancy_id": v["id"],
                        "name": v.get("name", ""),
                        "employer": v.get("employer", {}).get("name", ""),
                        "area": v.get("area", {}).get("name", ""),
                        "published_at": v.get("published_at", "")[:10],
                        "url": v.get("alternate_url", ""),
                    })

    if not rows:
        notifier.send("⚠️ Вакансии не найдены, CSV не создан.")
        return

    # --- запись CSV ---
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "vacancy_id",
                "name",
                "employer",
                "area",
                "published_at",
                "url",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # --- Telegram ---
    notifier.send_file(
        file_path=str(output_file),
        caption=f"📄 Собрано вакансий: {len(rows)}",
    )


if __name__ == "__main__":
    main()

