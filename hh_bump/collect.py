import csv
import requests
from pathlib import Path
from datetime import datetime, timezone

from hh_bump.config import Settings
from hh_bump.auth import get_valid_access_token
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramNotifier


CSV_FIELDS = [
    "vacancy_id",
    "name",
    "company",
    "area",
    "url",
    "published_at",
]


def save_csv(path: Path, vacancies: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for v in vacancies:
            writer.writerow(v)


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        token = get_valid_access_token()
        api = HHApi(s.api_base, token)
    except Exception as e:
        msg = f"❌ Ошибка токена: {e}"
        print(msg)
        notifier.send(msg)
        return 1

    output_file = Path(s.vacancies_output_file)
    all_vacancies: list[dict] = []

    searches_done = 0

    for text in s.apply_search_texts:
        for area in s.apply_areas:
            page = 0

            while page < s.apply_max_pages:
                if searches_done >= s.apply_max_searches_per_run:
                    print("⛔ Достигнут лимит запросов за запуск")
                    break

                print(
                    f"🔍 Поиск: text='{text}', area={area}, page={page}"
                )

                try:
                    items = api.search_vacancies(
                        text=text,
                        area=area,
                        page=page,
                        per_page=s.apply_per_page,
                    )
                except Exception as e:
                    print(f"❌ Ошибка поиска: {e}")
                    break

                print(f"   ↳ найдено: {len(items)} вакансий")

                if not items:
                    break

                for v in items:
                    all_vacancies.append(
                        {
                            "vacancy_id": v["id"],
                            "name": v["name"],
                            "company": v.get("employer", {}).get("name"),
                            "area": v.get("area", {}).get("name"),
                            "url": v.get("alternate_url"),
                            "published_at": v.get("published_at"),
                        }
                    )

                searches_done += 1
                page += 1

    # CSV создаётся ВСЕГДА
    save_csv(output_file, all_vacancies)

    if not all_vacancies:
        msg = "⚠️ Вакансии не найдены. CSV создан, но он пуст."
        print(msg)
        notifier.send(msg)
        return 0

    msg = (
        f"✅ Сбор завершён\n"
        f"Найдено вакансий: {len(all_vacancies)}\n"
        f"Файл: {output_file.name}"
    )
    print(msg)
    notifier.send_with_file(msg, output_file)

    return 0


if __name__ == "__main__":
    main()


