import random
import time
from hh_bump.api import HHApi
from hh_bump.config import Settings
from hh_bump.notifier import TelegramNotifier


def main():
    s = Settings()
    api = HHApi(s.api_base, s.access_token)
    notifier = TelegramNotifier()

    resumes = api.get_my_resumes()
    if not resumes:
        msg = "❌ У пользователя нет резюме."
        print(msg)
        notifier.send(msg)
        return

    total_applied = 0
    errors = 0
    searches_done = 0
    applied_vacancies = []  # для отчёта

    for text in s.apply_search_texts:
        if searches_done >= s.max_searches_per_run:
            print(f"⚠️ Достигнут лимит поисковых запросов ({s.max_searches_per_run}) за запуск")
            break

        try:
            vacancies = api.search_vacancies(
                text=text,
                areas=s.apply_areas,
                per_page=s.apply_per_page,
            )
            searches_done += 1
        except Exception as e:
            errors += 1
            print(f"❌ Ошибка поиска: {e}")
            continue

        if not vacancies:
            print(f"⚠️ Вакансии не найдены: «{text}» (регионы {','.join(map(str, s.apply_areas))})")
            continue

        for v in vacancies:
            if total_applied >= s.max_applications_per_run:
                print(f"⏹ Достигнут лимит откликов ({s.max_applications_per_run}) за запуск")
                break

            vacancy_id = v["id"]
            vacancy_name = v.get("name", "Без названия")
            employer = v.get("employer", {}).get("name", "")

            resume_id = random.choice(s.resume_ids)
            cover_letter = random.choice(s.cover_letters) if s.cover_letters else None

            try:
                result = api.apply_to_vacancy(vacancy_id, resume_id, cover_letter)
                if result is None:
                    # вакансии без доступного action
                    continue

                total_applied += 1
                applied_vacancies.append((vacancy_name, employer))
                msg = f"✅ Отклик отправлен: «{vacancy_name}» ({employer})"
                print(msg)
                notifier.send(msg)

                time.sleep(s.sleep_between_applies)
            except Exception as e:
                errors += 1
                print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")

    # Итоговый отчёт
    if applied_vacancies:
        summary = "📋 Итог по откликам:\n" + "\n".join(
            [f"- {name} ({emp})" for name, emp in applied_vacancies]
        )
        notifier.send(summary)
    else:
        msg = "⚠️ Подходящих вакансий для откликов не найдено."
        print(msg)
        notifier.send(msg)

    if errors:
        msg = f"⚠️ Ошибок при откликах: {errors}"
        print(msg)
        notifier.send(msg)


if __name__ == "__main__":
    main()

