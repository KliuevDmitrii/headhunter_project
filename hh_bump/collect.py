from datetime import datetime, timedelta, timezone
from pathlib import Path

from hh_bump.config import Settings
from hh_bump.api import HHApi
from hh_bump.auth import get_stored_access_token
from hh_bump.notifier import TelegramNotifier


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_html_report(vacancies: list[dict], path: Path):
    rows = []
    for v in vacancies:
        rows.append(
            f"""
            <tr>
                <td>{v['published_at']}</td>
                <td>{v['name']}</td>
                <td>{v['company']}</td>
                <td>{v['area']}</td>
                <td><a href="{v['url']}" target="_blank">Открыть</a></td>
            </tr>
            """
        )

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>HH вакансии</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
            }}
            h2 {{
                margin-bottom: 10px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 8px;
                vertical-align: top;
            }}
            th {{
                background-color: #f0f0f0;
            }}
            tr:nth-child(even) {{
                background-color: #fafafa;
            }}
            a {{
                color: #1a73e8;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <h2>Найденные вакансии ({len(vacancies)})</h2>
        <p>Отчёт сформирован: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        <table>
            <thead>
                <tr>
                    <th>Дата публикации</th>
                    <th>Вакансия</th>
                    <th>Компания</th>
                    <th>Регион</th>
                    <th>Ссылка</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </body>
    </html>
    """

    path.write_text(html, encoding="utf-8")


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

    vacancies_by_url: dict[str, dict] = {}
    searches_done = 0

    date_from = (
        datetime.now(timezone.utc) - timedelta(days=s.days_back)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    exclude_keywords = s.exclude_keywords
    exclude_companies = s.exclude_company_keywords

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

                for v in items:
                    name = (v.get("name") or "").lower()
                    company = (v.get("employer", {}).get("name") or "").lower()

                    if any(x in name for x in exclude_keywords):
                        continue

                    if any(x in company for x in exclude_companies):
                        continue

                    url = v.get("alternate_url")
                    if not url:
                        continue

                    published_at = v.get("published_at")
                    if not published_at:
                        continue

                    new_dt = parse_dt(published_at)

                    data = {
                        "id": v.get("id"),
                        "name": v.get("name"),
                        "company": v.get("employer", {}).get("name"),
                        "area": v.get("area", {}).get("name"),
                        "published_at": published_at,
                        "url": url,
                    }

                    if url in vacancies_by_url:
                        old_dt = parse_dt(vacancies_by_url[url]["published_at"])
                        if new_dt > old_dt:
                            vacancies_by_url[url] = data
                    else:
                        vacancies_by_url[url] = data

    vacancies = sorted(
        vacancies_by_url.values(),
        key=lambda x: parse_dt(x["published_at"]),
        reverse=True,
    )

    if not vacancies:
        notifier.send("⚠️ Вакансии за последние дни не найдены.")
        return

    output_file = Path(s.vacancies_output_file).with_suffix(".html")
    build_html_report(vacancies, output_file)

    msg = (
        "📄 <b>Отчёт по вакансиям</b>\n"
        f"🔎 Найдено: <b>{len(vacancies)}</b>\n"
        f"📅 За последние {s.days_back} дней\n"
        f"📎 Файл: {output_file.name}"
    )

    notifier.send(msg, file_path=output_file)


if __name__ == "__main__":
    main()
