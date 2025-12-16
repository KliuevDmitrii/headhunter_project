import requests


class HHApi:
    def __init__(self, api_base: str, token: str, app_name: str):
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {token}",
            "HH-User-Agent": app_name,
        }

    def search_vacancies(
        self,
        text: str,
        area: int,
        page: int,
        per_page: int,
    ) -> list[dict]:
        url = f"{self.api_base}/vacancies"
        params = {
            "text": text,
            "area": area,
            "page": page,
            "per_page": per_page,
        }

        r = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("items", [])
