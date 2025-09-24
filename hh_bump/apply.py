import random
import time
import requests

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
                    break  # дальше страниц нет

                vacancies_seen += len(vacancies)

                for v in vacancies:
                    if total_applied >= s.max_applications_per_run:
                        print(f"⏹ Достигнут лимит откликов ({s.max_applications_per_run})")
                        break

                    vacancy_id = v["id"]
                    vacancy_name = v.get("name", "Без названия")
                    employer = v.get("employer", {}).get("name", "")

                    resume_id = random.choice(s.resume_ids)
                    cover_letter = random.choice(s.cover_letters) if s.cover_letters else None

                    try:
                        result = api.apply_to_vacancy(vacancy_id, resume_id, cover_letter)
                        if result is None:
                            skipped += 1
                            print(f"⚠️ Пропуск: на «{vacancy_name}» нельзя откликнуться через API")
                            continue

                        total_applied += 1
                        applied_vacancies.append((vacancy_name, employer))
                        msg = f"✅ Отклик отправлен: «{vacancy_name}» ({employer})"
                        print(msg)
                        notifier.send(msg)

                        time.sleep(s.sleep_between_applies)

                    except requests.HTTPError as e:
                        if e.response.status_code == 404:
                            skipped += 1
                            print(f"⚠️ Пропуск: вакансия {vacancy_id} недоступна (404)")
                        else:
                            errors += 1
                            print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")
                    except Exception as e:
                        errors += 1
                        print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")

    # --- итоги ---
    summary_parts = []
    summary_parts.append(f"🔎 Поисковых запросов выполнено: {searches_done}")
    summary_parts.append(f"📑 Вакансий просмотрено: {vacancies_seen}")
    summary_parts.append(f"✅ Успешных откликов: {total_applied}")
    summary_parts.append(f"⚠️ Пропущено вакансий: {skipped}")
    summary_parts.append(f"❌ Ошибок: {errors}")

    if applied_vacancies:
        summary_parts.append("\n📋 Отклики отправлены:")
        summary_parts.extend([f"- {name} ({emp})" for name, emp in applied_vacancies])

    final_summary = "\n".join(summary_parts)
    print(final_summary)
    notifier.send(final_summary)


if __name__ == "__main__":
    main()
