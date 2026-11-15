from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from html import escape
import logging
import os
from pathlib import Path

import requests

from hh_bump.config import Settings
from hh_bump.api import HHApi
from hh_bump.notifier import TelegramError, TelegramNotifier

logger = logging.getLogger(__name__)


def parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_html_report(vacancies: list[dict], path: Path):
    rows = []
    for v in vacancies:
        v = {key: escape(str(value or ""), quote=True) for key, value in v.items()}
        rows.append(
            f"""
            <tr>
                <td>{v['published_at']}</td>
                <td>{v['name']}</td>
                <td>{v['company']}</td>
                <td style="text-align:center;">
                    <input type="checkbox">
                </td>
                <td>{v['area']}</td>
                <td>
                    <a href="{v['url']}" target="_blank">Открыть</a>
                </td>
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
            vertical-align: middle;
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
        input[type="checkbox"] {{
            transform: scale(1.2);
            cursor: pointer;
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
                <th>Просмотрено</th>
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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


@dataclass
class CollectionResult:
    vacancies: list[dict] = field(default_factory=list)
    searches_done: int = 0
    failed_searches: int = 0
    invalid_items: int = 0
    budget_reached: bool = False
    errors: list[str] = field(default_factory=list)


def collect_vacancies(s: Settings, api: HHApi) -> CollectionResult:
    if not s.search_texts or not s.areas:
        raise ValueError("Задайте search_texts и areas в config.ini")
    if not 1 <= s.per_page <= 100 or min(
        s.max_pages, s.max_searches_per_run, s.days_back
    ) < 1:
        raise ValueError("Неверные лимиты поиска в config.ini")

    result = CollectionResult()
    vacancies_by_url: dict[str, dict] = {}
    date_from = (datetime.now(timezone.utc) - timedelta(days=s.days_back)).strftime(
        "%Y-%m-%dT%H:%M:%S%z"
    )
    # Сначала первая страница всех запросов и регионов: один большой поиск
    # не должен расходовать весь бюджет и лишать остальные ключи результатов.
    active = list(dict.fromkeys((text, area) for text in s.search_texts for area in s.areas))
    for page in range(s.max_pages):
        next_page = []
        for text, area in active:
            if result.searches_done >= s.max_searches_per_run:
                result.budget_reached = True
                break
            result.searches_done += 1  # Неудачные запросы тоже расходуют бюджет.
            try:
                items = api.search_vacancies(
                    text=text, area=area, per_page=s.per_page,
                    page=page, date_from=date_from,
                )
            except (requests.RequestException, ValueError) as exc:
                result.failed_searches += 1
                result.errors.append(str(exc))
                logger.error("Ошибка HH [%s, area=%s, page=%s]: %s", text, area, page, exc)
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    if exc.response.status_code in (403, 429):
                        # Captcha или ограничение частоты: новые запросы усугубят сбой.
                        next_page = []
                        break
                continue

            # Проверяем исходную страницу, до фильтрации вакансий.
            if len(items) >= s.per_page:
                next_page.append((text, area))
            for v in items:
                try:
                    employer = v.get("employer") or {}
                    area_info = v.get("area") or {}
                    name = v.get("name") or ""
                    company = employer.get("name") or ""
                    if any(x in name.lower() for x in s.exclude_keywords):
                        continue
                    if any(x in company.lower() for x in s.exclude_company_keywords):
                        continue
                    url = v.get("alternate_url")
                    published_at = v.get("published_at")
                    if not url or not published_at:
                        result.invalid_items += 1
                        continue
                    new_dt = parse_dt(published_at)
                    data = {
                        "id": v.get("id"), "name": name, "company": company,
                        "area": area_info.get("name") or "",
                        "published_at": published_at, "url": url,
                    }
                    old = vacancies_by_url.get(url)
                    if old is None or new_dt > parse_dt(old["published_at"]):
                        vacancies_by_url[url] = data
                except (AttributeError, TypeError, ValueError):
                    result.invalid_items += 1
                    logger.warning("Пропущена вакансия с некорректными данными")

        if result.budget_reached or not next_page:
            break
        active = next_page

    result.vacancies = sorted(
        vacancies_by_url.values(), key=lambda v: parse_dt(v["published_at"]), reverse=True,
    )
    logger.info(
        "Поиск завершён: запросов=%d, ошибок=%d, вакансий=%d, некорректных записей=%d",
        result.searches_done, result.failed_searches, len(result.vacancies), result.invalid_items,
    )
    return result


def main():
    s = Settings()
    notifier = TelegramNotifier()
    if not s.hh_app_token:
        logger.warning(
            "HH_APP_TOKEN не задан: запрос без авторизации. "
            "HH документирует поиск с авторизацией приложения; "
            "при отказе настройте токен приложения из dev.hh.ru/admin."
        )
    with HHApi(api_base=s.api_base, app_name=s.app_name, token=s.hh_app_token) as api:
        result = collect_vacancies(s, api)

    if result.failed_searches or result.invalid_items:
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                # HTML-экранирование защищает разметку summary от данных сервера.
                stream.write("### Ошибка сбора вакансий\n\n")
                stream.write(f"Запросов: {result.searches_done}; ошибок: {result.failed_searches}.\n\n")
                for error in dict.fromkeys(result.errors):
                    stream.write(f"<pre>{escape(error)}</pre>\n")

    def send_notification(text, file_path=None):
        try:
            if file_path is None:
                notifier.send(text)
            else:
                notifier.send(text, file_path=file_path)
        except TelegramError as exc:
            logger.error("Ошибка доставки уведомления: %s", exc)
            summary = os.getenv("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as stream:
                    stream.write(f"### Ошибка Telegram\n\n<pre>{escape(str(exc))}</pre>\n")
            if result.failed_searches or result.invalid_items:
                raise RuntimeError(
                    "Сбой сбора HH и отдельный сбой доставки Telegram; "
                    "причины сохранены в журнале и сводке запуска"
                ) from exc
            raise

    warnings = []
    if result.failed_searches:
        warnings.append(f"⚠️ Подборка неполная: ошибок поиска — {result.failed_searches}.")
    if result.budget_reached:
        warnings.append("⚠️ Достигнут лимит запросов; просмотрены не все страницы.")
    if result.invalid_items:
        warnings.append(f"⚠️ Пропущено некорректных записей: {result.invalid_items}.")

    if result.vacancies:
        output_file = Path(s.vacancies_output_file).with_suffix(".html")
        build_html_report(result.vacancies, output_file)
        msg = (
            "📄 <b>Отчёт по вакансиям</b>\n"
            f"🔎 Найдено: <b>{len(result.vacancies)}</b>\n"
            f"📅 За последние {s.days_back} дней\n"
            f"📎 Файл: {escape(output_file.name)}"
        )
        if warnings:
            msg += "\n" + "\n".join(warnings)
        send_notification(msg, file_path=output_file)
    elif result.failed_searches or result.invalid_items:
        send_notification("❌ Не удалось собрать подборку.\n" + "\n".join(warnings))
    else:
        msg = "ℹ️ По заданным фильтрам вакансии за последние дни не найдены."
        if warnings:
            msg += "\n" + "\n".join(warnings)
        send_notification(msg)

    if result.failed_searches or result.invalid_items:
        # Не превращаем сбой API в зелёный запуск GitHub Actions.
        raise RuntimeError("Сбор вакансий завершён с ошибками; подробности выше в журнале")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
