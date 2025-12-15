import requests

class HHApi:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {token}",
            "HH-User-Agent": "hh-bump/1.0 (telegram bot)"
        }

    def get_my_resumes(self) -> dict[str, str]:
        url = f"{self.api_base}/resumes/mine"
        r = requests.get(url, headers=self.headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {
            item["id"]: item.get("title", "Без названия")
            for item in data.get("items", [])
        }

    def publish_resume(self, resume_id: str):
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)
        r.raise_for_status()
        return True

    def search_vacancies(
        self,
        text: str,
        area: int,
        per_page: int,
        page: int
    ) -> list[dict]:
        url = f"{self.api_base}/vacancies"
        params = {
            "text": text,
            "area": area,
            "per_page": per_page,
            "page": page,
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("items", [])
