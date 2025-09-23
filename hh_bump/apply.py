from datetime import datetime, timezone
import requests
import random

from .config import Settings
from .auth import (
    get_stored_access_token,
    refresh_access_token,
)
from .api import HHApi
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
            token = refresh_access_token(
                s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
            )
        api = HHApi(s.api_base, token)

        # Проверка токена
        try:
            resp = requests.get(
                f"{s.api_base}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 401:
                token = refresh_access_token(
                    s.oauth_token_url, s.client_id, s.client_secret, s.refresh_token
                )
                api = HHApi(s.api_base, token)
        except Exception:
            pass

        # Загружаем все резюме
        all_resumes = api.get_my_resumes()
        if not all_resumes:
            raise RuntimeError("Нет доступных резюме для откликов.")
        resume_ids = list(all_resumes.keys())

        # Выбираем резюме по часам (карусель)
        utc_now = datetime.now(timezone.utc)
        resume_index = utc_now.hour % len(resume_ids)
        resume_id = resume_ids[resume_index]
        resume_title = all_resumes[resume_id]

        # Загружаем сопроводительные письма
        letters = load_cover_letters(s.cover_letters)

        # Перебор ключевых слов и регионов
        for text in s.apply_texts:
            for area in s.apply_areas:
                try:
                    vacancies = api.search_vacancies(
                        text=text, area=area, per_page=s.apply_per_page
                    )
                    if not vacancies:
                        print(f"⚠️ Вакансии не найдены: «{text}» (регион {area})")
                        continue

                    for v in vacancies:
                        vid = v["id"]
                        title = v["name"]
                        message = random.choice(letters) if letters else None

                        try:
                            api.apply_to_vacancy(vid, resume_id, message=message)
                            msg = (
                                f"✅ Отклик отправлен: резюме «{resume_title}» "
                                f"→ вакансия «{title}» "
                                f"(поиск: «{text}», регион {area}, письмо: {'да' if message else 'нет'})"
                            )
                            print(msg)
                            notifier.send(msg)
                        except requests.exceptions.HTTPError as e:
                            if e.response is not None and e.response.status_code == 409:
                                msg = f"⚠️ Уже откликались на «{title}» (поиск: «{text}», регион {area})"
                                print(msg)
                                notifier.send(msg)
                            else:
                                raise
                except Exception as e:
                    print(f"❌ Ошибка поиска вакансий: {e}")

        return 0

    except Exception as e:
        msg = f"❌ Ошибка откликов: {e}"
        print(msg)
        notifier.send(msg)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
