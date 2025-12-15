import csv
import requests
from pathlib import Path

from hh_bump.api import HHApi
from hh_bump.config import Settings
from hh_bump.notifier import TelegramNotifier
from hh_bump.auth import get_stored_access_token, refresh_access_token


def main():
    s = Settings()
    notifier = TelegramNotifier()

    # --- токен ---
    try:
        token = get_stored_access_token()
        if not token:
            token = refresh_access_token(
                s.oauth_token_url,
                s.client_id,
                s.client_secret,
                s.refresh_token,
            )

        api = HHApi(s.api_base, token)
    except Exception as e:
        notifier.send(f"❌ Ошибка токена: {e}")
        return

    output_file = Path(s.vacancies_output_file)
    if output_file.exists():
        output_file.unlink()  # всегда перезаписываем файл

    rows = []
    searches_done = 0
    total_found = 0
    excluded = 0

    for text in s.search_texts:
        print(f"\n🔍 Поиск по ключу: «{text}»")

        for area in s.areas:
            for page in range(s.max_pages):
                if searches_done >= s.max_searches_per_run:
                    break

                try:
                    vacancies = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.per_page,
                        page=page,
                    )
                    searches_done += 1
                except Exception as e:
                    print(f"❌ Ошибка поиска [{text}, area={area}, page={page}]: {e}")
                    continue

                if not vacancies:
                    break

                for v in vacancies:
                    total_found += 1

                    name = v.get("name", "")
                    name_lc = name.lower()

                    # --- фильтр исключений ---
                    if any(word in name_lc for word in s.exclude_keywords):
                        excluded += 1
                        continue

                    rows.append({
                        "id": v.get("id"),
                        "name": name,
                        "employer": v.get("employer", {}).get("name", ""),
                        "area": v.get("area", {}).get("name", ""),
                        "url": v.get("alternate_url"),
                    })

    if not rows:
        notifier.send("⚠️ Вакансии не найдены, CSV не создан.")
        return

    # --- запись CSV ---
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "name", "employer", "area", "url"],
        )
        writer.writeheader()
        writer.writerows(rows)

    msg = (
        "📄 Сбор вакансий завершён\n"
        f"🔎 Поисковых запросов: {searches_done}\n"
        f"📑 Найдено вакансий: {total_found}\n"
        f"🚫 Исключено по фильтру: {excluded}\n"
        f"📎 Файл: {output_file.name}"
    )

    notifier.send(msg, file_path=output_file)


if __name__ == "__main__":
    main()




