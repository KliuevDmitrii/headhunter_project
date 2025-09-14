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
        data = r.json()
        return {
            item["id"]: item.get("title", "Без названия")
            for item in data.get("items", [])
        }

    def publish_resume(self, resume_id: str):
        """
        Поднять резюме (обновить дату публикации).
        """
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()
