import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hh_bump.config import Settings
from hh_bump.api import HHApi
from hh_bump.auth import get_stored_access_token
from hh_bump.notifier import TelegramNotifier


def parse_dt(value: str) -> datetime:
    """HH отдаёт ISO-дату — приводим к datetime"""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    s = Settings()
    notifier = TelegramNotifier()

    token = get_stored_access_token()
    if not token:
        notifier.send("❌ Нет access_token для сбора вакансий")
        return

    api = HHApi(
        api_base=s.api_base,
        token=token,
        app_name=s.app_name,
    )

    output_file = Path(s.vacancies_output_file)

    # 🔑 ключ = url, значение = вакансия
    вакансии_по_url: dict[str, dict] = {}

    searches_done = 0

    date_from = (
        datetime.now(timezone.utc) - timedelta(days=s.days_back)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    exclude_keywords = s.exclude_keywords
    exclude_company_keywords = s.exclude_company_keywords

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
                    name = v.get("name") or ""
                    vacancy_name = name.lower()

                    company = v.get("employer", {}).get("name") or ""
                    company_name = company.lower()

                    url = v.get("alternate_url")
                    published_at = v.get("published_at")

                    if not url or not published_at:
                        continue

                    # ❌ фильтр по названию вакансии
                    if any(x in vacancy_name for x in exclude_keywords):
                        continue

                    # ❌ фильтр по компании
                    if any(x in company_name for x in exclude_company_keywords):
                        continue

                    new_dt = parse_dt(published_at)

                    vacancy_data = {
                        "id": v.get("id"),
                        "name": name,
                        "company": company,
                        "area": v.get("area", {}).get("name"),
                        "published_at": published_at,
                        "url": url,
                    }

                    # 🔁 дедупликация по URL
                    if url in вакансии_по_url:
                        old_dt = parse_dt(вакансии_по_url[url]["published_at"])
                        if new_dt > old_dt:
                            вакансии_по_url[url] = vacancy_data
                    else:
                        вакансии_по_url[url] = vacancy_data

    vacancies = list(вакансии_по_url.values())

    if not vacancies:
        msg = "⚠️ Вакансии за последние дни не найдены."
        print(msg)
        notifier.send(msg)
        return

    # 📊 сортируем по дате (сначала новые)
    vacancies.sort(
        key=lambda x: parse_dt(x["published_at"]),
        reverse=True,
    )

    # --- CSV ---
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
        f"📑 Уникальных вакансий: {len(vacancies)}\n"
        f"📎 Файл: {output_file.name}"
    )
    print(msg)
    notifier.send(msg, file_path=output_file)


if __name__ == "__main__":
    main()
