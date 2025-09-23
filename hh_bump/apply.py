import random
import time
from hh_bump.config import Settings
from hh_bump.auth import get_stored_access_token, refresh_access_token, store_access_token
from hh_bump.api import HHApi
from .notifier import TelegramNotifier


def load_cover_letters(paths: list[str]) -> list[str]:
    """Загружает сопроводительные письма из файлов."""
    letters = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    letters.append(content)
        except FileNotFoundError:
            continue
    return letters


def main():
    s = Settings()
    notifier = TelegramNotifier()

    try:
        # Авторизация
        token = get_stored_access_token()
        if not token:
            token = refresh_access_token(s.client_id, s.client_secret, s.refresh_token)
            store_access_token(token)

        api = HHApi(s.api_base, token)

        # Загружаем резюме
        all_resumes = api.get_my_resumes()
        if not all_resumes:
            msg = "❌ Нет доступных резюме для откликов."
            print(msg)
            notifier.send(msg)
            return 1

        # Загружаем письма
        letters = load_cover_letters(s.cover_letters)

        applied_count = 0
        error_count = 0

        for text in s.apply_texts:
            for area in s.apply_areas:
                try:
                    vacancies = api.search_vacancies(
                        text=text,
                        area=area,
                        per_page=s.apply_per_page,
                    )
                except Exception as e:
                    print(f"❌ Ошибка поиска вакансий: {e}")
                    error_count += 1
                    continue

                if not vacancies:
                    print(f"⚠️ Вакансии не найдены: «{text}» (регион {area})")
                    continue

                for v in vacancies:
                    if applied_count >= s.max_applications_per_run:
                        msg = f"⚠️ Достигнут лимит откликов ({s.max_applications_per_run}) за запуск."
                        print(msg)
                        notifier.send(msg)
                        # в этот момент отправим статистику по ошибкам
                        if error_count > 0:
                            notifier.send(f"⚠️ Ошибок при откликах: {error_count}")
                        return 0

                    vacancy_id = v["id"]
                    vacancy_name = v.get("name", "Без названия")

                    # случайное резюме
                    resume_id = random.choice(list(all_resumes.keys()))
                    resume_title = all_resumes[resume_id]

                    # случайное сопроводительное письмо
                    message = random.choice(letters) if letters else None

                    try:
                        result = api.apply_to_vacancy(vacancy_id, resume_id, message)
                        if result is None:
                            print(f"⚠️ Вакансия «{vacancy_name}» ({vacancy_id}) не принимает отклики")
                            error_count += 1
                            continue

                        msg = (
                            f"✅ Отклик отправлен: резюме «{resume_title}» "
                            f"→ вакансия «{vacancy_name}» (регион {area}, письмо: {'да' if message else 'нет'})"
                        )
                        print(msg)
                        notifier.send(msg)
                        applied_count += 1

                        # пауза
                        time.sleep(s.sleep_between_applies)

                    except Exception as e:
                        print(f"❌ Ошибка отклика на «{vacancy_name}»: {e}")
                        error_count += 1

        if applied_count == 0:
            msg = "⚠️ Подходящих вакансий для откликов не найдено."
            print(msg)
            notifier.send(msg)

        # отправляем итог по ошибкам
        if error_count > 0:
            summary = f"⚠️ Ошибок при откликах: {error_count}"
            print(summary)
            notifier.send(summary)

        return 0

    except Exception as e:
        msg = f"❌ Ошибка выполнения apply.py: {e}"
        print(msg)
        notifier.send(msg)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


