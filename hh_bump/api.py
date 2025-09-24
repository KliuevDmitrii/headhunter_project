import requests


class HHApi:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base
        self.headers = {"Authorization": f"Bearer {token}"}

    def get_my_resumes(self) -> dict[str, str]:
        """
        Возвращает словарь {id: title} для всех резюме пользователя.
        Если у резюме нет названия, подставляет "Без названия".
        """
        url = f"{self.api_base}/resumes/mine"
        r = requests.get(url, headers=self.headers, timeout=30)
        r.raise_for_status()

        try:
            data = r.json()
        except ValueError:
            raise RuntimeError(f"Ошибка при получении списка резюме: {r.text[:200]}")

        return {
            item["id"]: item.get("title", "Без названия")
            for item in data.get("items", [])
        }

    def publish_resume(self, resume_id: str):
        """
        Поднять резюме (обновить дату публикации).
        HH API может вернуть 204 No Content,
        поэтому json() парсить не всегда нужно.
        """
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)
        r.raise_for_status()

        if not r.text.strip():
            return None  # Успех без тела
        try:
            return r.json()
        except ValueError:
            return {"raw_response": r.text[:200]}
        
    def search_vacancies(
        self, text: str, area: int = 1, per_page: int = 20, page: int = 0
    ) -> list[dict]:
        """
        Поиск вакансий по ключевым словам.
        """
        url = f"{self.api_base}/vacancies"
        params = {
        "text": text,
        "area": area,
        "per_page": per_page,
        "page": page,
        "search_field": "name",   # искать по названию вакансии
        "period": 1             # вакансии только за последние сутки
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("items", [])

    def apply_to_vacancy(self, vacancy_id: str, resume_id: str, message: str | None = None):
        """
        Отправить отклик на вакансию (если доступен action 'negotiations').
        """
        vacancy_url = f"{self.api_base}/vacancies/{vacancy_id}"
        r = requests.get(vacancy_url, headers=self.headers, timeout=30)
        r.raise_for_status()
        vacancy = r.json()

        actions = vacancy.get("actions", {})
        negotiations = actions.get("negotiations")
        if not negotiations:
            return None  # нельзя откликнуться через API

        method = negotiations.get("method", "POST").upper()
        url = negotiations["url"]

        if method != "POST":
            raise RuntimeError(f"Неожиданный метод отклика: {method}")

        payload = {"resume_id": resume_id}
        if message:
            payload["message"] = message

        r = requests.post(url, headers=self.headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json() if r.text.strip() else {"status": "ok"}
