import requests


class HHApi:
    def __init__(self, api_base: str, app_name: str, token: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.app_name = app_name
        self.token = token

    # ========= HEADERS =========

    def _public_headers(self) -> dict:
        """
        Заголовки для публичных запросов (поиск вакансий).
        Authorization НЕ нужен.
        """
        return {
            "HH-User-Agent": self.app_name,
        }

    def _auth_headers(self) -> dict:
        """
        Заголовки для запросов соискателя (резюме).
        """
        if not self.token:
            raise RuntimeError("Нет access_token для авторизованного запроса")

        return {
            "Authorization": f"Bearer {self.token}",
            "HH-User-Agent": self.app_name,
        }

    # ========= VACANCIES (PUBLIC API) =========

    def search_vacancies(
        self,
        text: str,
        area: int,
        per_page: int,
        page: int,
        date_from: str | None = None,
    ) -> list[dict]:
        """
        Поиск вакансий (публичный endpoint).
        """

        url = f"{self.api_base}/vacancies"

        params = {
            "text": text,
            "area": area,
            "page": page,
            "per_page": per_page,
        }

        if date_from:
            params["date_from"] = date_from

        r = requests.get(
            url,
            headers=self._public_headers(),  # ✅ ВАЖНО
            params=params,
            timeout=30,
        )
        r.raise_for_status()

        return r.json().get("items", [])

    # ========= RESUMES (AUTH API) =========

    def get_my_resumes(self) -> list[dict]:
        """
        Получить список резюме пользователя.
        """
        r = requests.get(
            f"{self.api_base}/resumes/mine",
            headers=self._auth_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("items", [])

    def publish_resume(self, resume_id: str):
        """
        Поднять (обновить) резюме.
        """
        r = requests.post(
            f"{self.api_base}/resumes/{resume_id}/publish",
            headers=self._auth_headers(),
            timeout=30,
        )
        r.raise_for_status()


