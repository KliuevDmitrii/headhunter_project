import requests


class HHApi:
    def __init__(self, api_base: str, access_token: str):
        self.api_base = api_base.rstrip("/")
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get_my_resume_ids(self):
        r = requests.get(f"{self.api_base}/resumes/mine",
                         headers=self.headers, timeout=30
                         )
        r.raise_for_status()
        items = r.json().get("items", [])
        return [it["id"] for it in items]

    def publish_resume(self, resume_id: str):
        r = requests.post(f"{self.api_base}/resumes/{resume_id}/publish",
                          headers=self.headers, timeout=30
                          )
        if r.status_code not in (200, 204):
            r.raise_for_status()
