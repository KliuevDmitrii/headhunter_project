import os
import random
from hh_bump.config import Settings
from hh_bump.auth import get_stored_access_token, refresh_access_token, store_access_token
from hh_bump.api import HHApi
from .notifier import TelegramNotifier


def main():
    try:
        s = Settings()
        notifier = TelegramNotifier()

        token = get_stored_access_token()
        if not token:
            token = refresh_access_token(s.client_id, s.client_secret, s.refresh_token)
            store_access_token(token)

        api = HHApi(s.api_base, token)

        # список резюме пользователя (id -> title)
        resumes = api.get_my_resumes()
        if not resumes:
            msg = "❌ У пользователя нет доступных резюме"
            print(msg)
            notifier.send(msg)
            return 1

        # список ключевых слов и регионов
        keywords = [
            "Тестировщик",
            "QA engineer",
            "QA Automation",
            "QA",
            "QA-инженер",
            "Manual QA",
            "Инженер по тестированию",
            "Инженер-тестировщик",
            "Software Tester",
            "Software Test Engineer",
            "Software QA Engineer",
            "Software Quality Engineer",
            "Software Quality Assurance Engineer",
            "Специалист по тестированию"
        ]
        areas = [113, 28, 40, 16, 97, 100, 9, 3, 48]

        applied_count = 0

        for kw in keywords:
            for area in areas:
                try:
                    vacancies = api.search_vacancies(kw, area=area, per_page=10)
                except Exception as e:
                    print(f"❌ Ошибка поиска вакансий: {e}")
                    continue

                if not vacancies:
                    print(f"⚠️ Вакансии не найдены: «{kw}» (регион {area})")
                    continue

                for v in vacancies:
                    vacancy_id = v["id"]
                    vacancy_name = v.get("name", "Без названия")

                    # случайное резюме
                    resume_id = random.choice(list(resumes.keys()))
                    resume_name = resumes[resume_id]

                    # случайное сопроводительное письмо (если есть)
                    message = None
                    if s.cover_letters:
                        message = random.choice(s.cover_letters)

                    try:
                        result = api.apply_to_vacancy(vacancy_id, resume_id, message)
                        if result is None:
                            print(f"⚠️ Вакансия «{vacancy_name}» ({vacancy_id}) не принимает отклики через API, пропуск")
                            continue

                        msg = f"✅ Отклик отправлен на «{vacancy_name}» (регион {area}) резюме «{resume_name}»"
                        print(msg)
                        notifier.send(msg)
                        applied_count += 1
                    except Exception as e:
                        msg = f"❌ Ошибка отклика: {e}"
                        print(msg)
                        notifier.send(msg)

        if applied_count == 0:
            msg = "⚠️ Подходящих вакансий для откликов не найдено"
            print(msg)
            notifier.send(msg)

        return 0

    except Exception as e:
        msg = f"❌ Ошибка откликов: {e}"
        print(msg)
        notifier.send(msg)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

