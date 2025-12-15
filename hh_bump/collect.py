import csv
from pathlib import Path

from hh_bump.api import HHApi
from hh_bump.auth import get_valid_access_token
from hh_bump.config import Settings
from hh_bump.notifier import TelegramNotifier


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
        return

    output_file = Path(s.vacancies_output_file)
    vacancies = []
    searches_done = 0

    for text in s.search_texts:
        print(f"\n🔍 Поиск по ключу: «{text}»")

        for area in s.areas:
            for page in range(s.max_pages):
                if searches_done >= s.max_searches_per_run:
                    print("⚠️ Достигнут лимит поисковых запросов")
                    break

                try:
                    items = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.per_page,
                        page=page,
                    )
                    searches_done += 1
                except Exception as e:
                    print(f"❌ Ошибка поиска [{text}, area={area}, page={page}]: {e}")
                    continue

                if not items:
                    break

                for v in items:
                    vacancies.append({
                        "vacancy_id": v.get("id"),
                        "name": v.get("name"),
                        "employer": v.get("employer", {}).get("name"),
                        "area": v.get("area", {}).get("name"),
                        "url": v.get("alternate_url"),
                    })

    if not vacancies:
        msg = "⚠️ Вакансии не найдены, CSV не создан."
        print(msg)
        notifier.send(msg)
        return

    # перезаписываем файл каждый запуск
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["vacancy_id", "name", "employer", "area", "url"]
        )
        writer.writeheader()
        writer.writerows(vacancies)

    msg = (
        f"📄 Сбор вакансий завершён\n"
        f"🔎 Поисковых запросов: {searches_done}\n"
        f"📑 Найдено вакансий: {len(vacancies)}\n"
        f"📎 Файл: {output_file.name}"
    )

    print(msg)
    notifier.send(msg, file_path=output_file)


if __name__ == "__main__":
    main()



