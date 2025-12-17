import requests


class HHApi:
    def __init__(self, api_base: str, app_name: str, token: str | None = None):
        self.api_base = api_base
        self.app_name = app_name
        self.token = token

    # ===== headers =====

    def _public_headers(self) -> dict:
        # 🔴 БЕЗ Authorization
        return {
            "HH-User-Agent": self.app_name,
        }

    def _auth_headers(self) -> dict:
        # 🟢 С Authorization
        return {
            "Authorization": f"Bearer {self.token}",
            "HH-User-Agent": self.app_name,
        }

    # ===== вакансии (ТОЛЬКО public) =====

    def search_vacancies(
        self,
        text: str,
        area: int,
        per_page: int,
        page: int,
        date_from: str | None = None,
    ) -> list[dict]:
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
            headers=self.headers,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("items", [])

    # ===== резюме (ТОЛЬКО auth) =====

    def get_my_resumes(self):
        r = requests.get(
            f"{self.api_base}/resumes/mine",
            headers=self._auth_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["items"]

    def publish_resume(self, resume_id: str):
        r = requests.post(
            f"{self.api_base}/resumes/{resume_id}/publish",
            headers=self._auth_headers(),
            timeout=30,
        )
        r.raise_for_status()


