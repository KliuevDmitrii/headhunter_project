import requests


class HHApi:
    def __init__(self, api_base: str, access_token: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.headers = {
            "User-Agent": "hh-vacancy-collector/1.0",
        }
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    def search_vacancies(
        self,
        text: str,
        area: int,
        page: int = 0,
        per_page: int = 20,
    ) -> list[dict]:
        """
        Поиск вакансий (ТОЛЬКО публичный эндпоинт).
        Работает без applicant-доступа.
        """
        url = f"{self.api_base}/vacancies"
        params = {
            "text": text,
            "area": area,
            "page": page,
            "per_page": per_page,
        }

        resp = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()

        data = resp.json()
        return data.get("items", [])
