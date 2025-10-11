import random
import time
import requests
import csv
from datetime import datetime
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
                s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
            )

        api = HHApi(s.api_base, token)

        # проверка токена
        resp = requests.get(
            f"{s.api_base}/me", headers={"Authorization": f"Bearer {token}"}, timeout=15
        )
        if resp.status_code == 401:
            token = refresh_access_token(
                s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
            )
            api = HHApi(s.api_base, token)
    except Exception as e:
        msg = f"❌ Ошибка получения токена: {e}"
        print(msg)
        notifier.send(msg)
        return

    # --- резюме ---
    resumes = api.get_my_resumes()
    if not resumes:
        msg = "❌ У пользователя нет резюме."
        print(msg)
        notifier.send(msg)
        return

    total_applied = 0
    skipped = 0
    errors = 0
    searches_done = 0
    vacancies_seen = 0
    applied_vacancies = []
    all_vacancies_log = []

    # --- основной цикл поиска и откликов ---
    for text in s.apply_search_texts:
        print(f"\n🔍 Обработка ключа: «{text}»")

        for area in s.apply_areas:
            for page in range(s.apply_max_pages):
                if searches_done >= s.max_searches_per_run:
                    print(f"⚠️ Лимит поисковых запросов ({s.max_searches_per_run})")
                    break

                try:
                    vacancies = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.apply_per_page,
                        page=page,
                    )
                    searches_done += 1
                except Exception as e:
                    errors += 1
                    print(f"❌ Ошибка поиска [{text}, area={area}, page={page}]: {e}")
                    continue

                if not vacancies:
                    break

                vacancies_seen += len(vacancies)

                for v in vacancies:
                    vacancy_id = v["id"]
                    vacancy_name = v.get("name", "Без названия")
                    employer = v.get("employer", {}).get("name", "")
                    vacancy_url = f"https://hh.ru/vacancy/{vacancy_id}"

                    status = "не обработана"
                    all_vacancies_log.append([vacancy_name, employer, vacancy_url, text, area, status])

                    if total_applied >= s.max_applications_per_run:
                        print(f"⏹ Достигнут лимит откликов ({s.max_applications_per_run})")
                        break

                    resume_id = random.choice(s.resume_ids)
                    cover_letter = random.choice(s.cover_letters) if s.cover_letters else None

                    try:
                        result = api.apply_to_vacancy(vacancy_id, resume_id, cover_letter)
                        if result is None:
                            skipped += 1
                            status = "нельзя откликнуться через API"
                            print(f"⚠️ Пропуск: на «{vacancy_name}» нельзя откликнуться через API")
                            continue

                        total_applied += 1
                        status = "отклик отправлен"
                        applied_vacancies.append((vacancy_name, employer))
                        print(f"✅ Отклик отправлен: «{vacancy_name}» ({employer})")

                        time.sleep(s.sleep_between_applies)

                    except requests.HTTPError as e:
                        if e.response.status_code == 404:
                            skipped += 1
                            status = "вакансия недоступна (404)"
                            print(f"⚠️ Пропуск: вакансия {vacancy_id} недоступна (404)")
                        else:
                            errors += 1
                            status = f"ошибка HTTP {e.response.status_code}"
                            print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")
                    except Exception as e:
                        errors += 1
                        status = f"ошибка {type(e).__name__}"
                        print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")

                    all_vacancies_log[-1][-1] = status

    # --- сохраняем CSV ---
    try:
        out_dir = Path("hh_bump/logs")
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / "found_vacancies.csv"

        # 🧹 удаляем старый файл, если есть
        if csv_path.exists():
            csv_path.unlink()

        # 💾 создаём новый CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Название", "Компания", "Ссылка", "Ключ", "Регион", "Статус"])
            writer.writerows(all_vacancies_log)

        print(f"💾 Вакансии сохранены в {csv_path}")
        notifier.send_file(csv_path, caption="💾 Отчёт по найденным вакансиям (автоотклики)")

    except Exception as e:
        print(f"⚠️ Ошибка при сохранении/отправке CSV: {e}")

    # --- итог ---
    summary_parts = [
        f"🔎 Поисковых запросов: {searches_done}",
        f"📑 Вакансий просмотрено: {vacancies_seen}",
        f"✅ Успешных откликов: {total_applied}",
        f"⚠️ Пропущено вакансий: {skipped}",
        f"❌ Ошибок: {errors}",
    ]

    if applied_vacancies:
        summary_parts.append("\n📋 Отклики отправлены:")
        summary_parts.extend([f"- {name} ({emp})" for name, emp in applied_vacancies])

    final_summary = "\n".join(summary_parts)
    print(final_summary)
    notifier.send(final_summary)


if __name__ == "__main__":
    main()

