import requests


class HHApi:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    # --- резюме ---
    def get_my_resumes(self) -> dict[str, str]:
        """Возвращает словарь {id: title} для всех резюме пользователя."""
        url = f"{self.api_base}/resumes/mine"
        r = requests.get(url, headers=self.headers, timeout=30)
        r.raise_for_status()

        try:
            data = r.json()
        except ValueError:
            raise RuntimeError(f"Ошибка при получении списка резюме: {r.text[:200]}")

        return {item["id"]: item.get("title", "Без названия") for item in data.get("items", [])}

    # --- поднятие резюме ---
    def publish_resume(self, resume_id: str):
        """Поднять резюме (обновить дату публикации)."""
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)
        r.raise_for_status()

        if not r.text.strip():
            return None
        try:
            return r.json()
        except ValueError:
            return {"raw_response": r.text[:200]}

    # --- поиск вакансий ---
    def search_vacancies(self, text: str, area: int = 1, per_page: int = 20, page: int = 0) -> list[dict]:
        """
        Поиск вакансий по ключевым словам (только свежие за 2 дня).
        """
        url = f"{self.api_base}/vacancies"
        params = {
            "text": text,
            "area": area,
            "per_page": per_page,
            "page": page,
            "search_field": "name",
            "period": 2,
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("items", [])

    # --- отклик ---
    def apply_to_vacancy(self, vacancy_id: str, resume_id: str, message: str | None = None):
        """
        Отправить отклик на вакансию.
        1️⃣ Если есть 'actions.negotiations' → обычный API.
        2️⃣ Если нет — пытаемся откликнуться через popup (в том числе при отклике на вакансии в другой стране).
        """
        # --- стандартный API-отклик ---
        vacancy_url = f"{self.api_base}/vacancies/{vacancy_id}"
        r = requests.get(vacancy_url, headers=self.headers, timeout=30)
        r.raise_for_status()
        vacancy = r.json()

        actions = vacancy.get("actions", {})
        negotiations = actions.get("negotiations")

        if negotiations:
            url = negotiations.get("url")
            method = negotiations.get("method", "POST").upper()
            if method != "POST":
                raise RuntimeError(f"Неожиданный метод отклика: {method}")

            payload = {"resume_id": resume_id}
            if message:
                payload["message"] = message

            r = requests.post(url, headers=self.headers, json=payload, timeout=30)
            r.raise_for_status()
            return r.json() if r.text.strip() else {"status": "ok"}

        # --- fallback через popup ---
        popup_url = "https://hh.ru/applicant/vacancy_response/popup"
        params = {
            "vacancyId": vacancy_id,
            "isTest": "no",
            "withoutTest": "no",
            "lux": "true",
            "alreadyApplied": "false"
        }
        popup_resp = requests.get(popup_url, headers=self.headers, params=params, timeout=30)
        if popup_resp.status_code != 200:
            return None

        try:
            popup_json = popup_resp.json()
        except ValueError:
            return None

        # Проверяем можно ли откликнуться
        if popup_json.get("responseImpossible") is True:
            return None

        # --- выполняем POST отклик ---
        apply_url = "https://hh.ru/applicant/vacancy_response"
        payload = {
            "vacancy_id": vacancy_id,
            "resume_hash": resume_id,
            "hhtmFrom": "vacancy_search_list",
            "lux": "true",
            "isTest": "no",
            "withoutTest": "no",
            "alreadyApplied": "false",
        }
        if message:
            payload["letter"] = message

        resp = requests.post(apply_url, headers=self.headers, data=payload, timeout=30)
        if resp.status_code in (200, 201, 204):
            return {"status": "ok", "via": "popup-force"}

        return None
