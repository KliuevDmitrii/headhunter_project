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
        2️⃣ Если нет — пытаемся откликнуться через popup fallback.
        """
        # --- пробуем стандартный отклик ---
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

        # --- fallback: popup /applicant/vacancy_response ---
        popup_url = f"https://hh.ru/applicant/vacancy_response/popup"
        params = {"vacancyId": vacancy_id}
        popup_resp = requests.get(popup_url, headers=self.headers, params=params, timeout=30)

        if popup_resp.status_code != 200:
            return None  # fallback не сработал

        try:
            popup_json = popup_resp.json()
        except ValueError:
            return None

        # если popup разрешает отклик
        resp_status = popup_json.get("responseStatus", {})
        allowed = popup_json.get("responsePopup") or {}
        allowed_flag = (
            popup_json.get("responseImpossible") is False
            and popup_json.get("relocationWarning", {}).get("show") is not True
        )

        if not allowed_flag:
            return None

        # финальный отклик через popup API
        resp_url = "https://hh.ru/applicant/vacancy_response"
        payload = {
            "vacancy_id": vacancy_id,
            "resume_hash": resume_id,
            "hhtmFrom": "vacancy_search_list",
        }
        if message:
            payload["letter"] = message

        post_resp = requests.post(resp_url, headers=self.headers, data=payload, timeout=30)
        if post_resp.status_code in (200, 201, 204):
            return {"status": "ok", "via": "popup"}

        return None
