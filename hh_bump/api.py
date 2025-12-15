import requests

class HHApi:
    def __init__(self, api_base: str, access_token: str):
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "hh-bump-bot/1.0",
            "Accept": "application/json",
        }

    def publish_resume(self, resume_id: str):
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)

        # 204 — успех (нормально!)
        if r.status_code == 204:
            return True

        # 429 — cooldown
        if r.status_code == 429:
            raise requests.HTTPError(
                "Resume cooldown",
                response=r
            )

        # всё остальное — ошибка
        r.raise_for_status()