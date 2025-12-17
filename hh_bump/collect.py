import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hh_bump.config import Settings
from hh_bump.api import HHApi
from hh_bump.auth import get_stored_access_token
from hh_bump.notifier import TelegramNotifier


def main():
    s = Settings()
    notifier = TelegramNotifier()

    token = get_stored_access_token()
    api = HHApi(s.api_base, token, s.app_name)

    output_file = Path(s.vacancies_output_file)
    vacancies = []
    searches_done = 0

    date_from = (
        datetime.now(timezone.utc) - timedelta(days=s.days_back)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    for text in s.search_texts:
        print(f"\n🔍 Поиск по ключу: «{text}»")

        for area in s.areas:
            for page in range(s.max_pages):
                if searches_done >= s.max_searches_per_run:
                    break

                try:
                    items = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.per_page,
                        page=page,
                        date_from=date_from,
                    )
                    searches_done += 1
                except Exception as e:
                    print(f"❌ Ошибка поиска [{text}, area={area}, page={page}]: {e}")
                    continue

                if not items:
                    break

                for v in items:
                    name = v.get("name", "").lower()

                    if any(x in name for x in s.exclude_keywords):
                        continue

                    vacancies.append({
                        "id": v.get("id"),
                        "name": v.get("name"),
                        "company": v.get("employer", {}).get("name"),
                        "area": v.get("area", {}).get("name"),
                        "published_at": v.get("published_at"),
                        "url": v.get("alternate_url"),
                    })

    if not vacancies:
        msg = "⚠️ Вакансии за последние дни не найдены."
        print(msg)
        notifier.send(msg)
        return

    # CSV
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=vacancies[0].keys(),
        )
        writer.writeheader()
        writer.writerows(vacancies)

    msg = (
        "📄 Сбор вакансий завершён\n"
        f"🔎 Поисковых запросов: {searches_done}\n"
        f"📑 Найдено вакансий: {len(vacancies)}\n"
        f"📎 Файл: {output_file.name}"
    )
    print(msg)
    notifier.send(msg, file_path=output_file)


if __name__ == "__main__":
    main()






