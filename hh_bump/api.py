import requests


class HHApi:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip("/")
        # Важно: HH любит, когда есть User-Agent
        self.headers = {
            "Authorization": f"Bearer {token}",
            "HH-User-Agent": "hh-bump/1.0 (kliuevdmitrii@gmail.com)",
        }

    def get_my_resumes(self) -> dict[str, str]:
        """
        Возвращает словарь {resume_id: title}.
        resume_id здесь — именно ID резюме (числовой), который нужен для /resumes/{id}/publish.
        """
        url = f"{self.api_base}/resumes/mine"
        r = requests.get(url, headers=self.headers, timeout=30)

        # Если тут 403/401 — проблема почти всегда в токене/правах (не applicant токен)
        r.raise_for_status()

        data = r.json()
        items = data.get("items", []) or []

        result: dict[str, str] = {}
        for item in items:
            rid = str(item.get("id"))  # это числовой ID резюме
            title = item.get("title") or "Без названия"
            if rid and rid != "None":
                result[rid] = title
        return result

    def publish_resume(self, resume_id: str) -> bool:
        """
        Поднимаем резюме.
        Успех: 204 No Content
        Cooldown: 429
        Остальное: raise_for_status()
        """
        url = f"{self.api_base}/resumes/{resume_id}/publish"
        r = requests.post(url, headers=self.headers, timeout=30)

        if r.status_code == 204:
            return True

        if r.status_code == 429:
            # пусть main.py решает "пропустить и попробовать следующее"
            raise requests.HTTPError("Resume cooldown (429)", response=r)

        r.raise_for_status()
        return True
