import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HHApi:
    def __init__(self, api_base: str, app_name: str, token: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.app_name = app_name
        self.token = token
        self.session = requests.Session()
        # Повторяем только безопасные GET при временных сбоях.
        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=False,
        )
        for scheme in ("https://", "http://"):
            self.session.mount(scheme, HTTPAdapter(max_retries=retries))

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ========= HEADERS =========

    def _vacancy_headers(self) -> dict:
        """
        Поиск поддерживает токен приложения; токен соискателя не используется.
        """
        headers = {"HH-User-Agent": self.app_name}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _raise_search_error(response):
        if response.status_code < 400:
            return
        # Не выводим весь ответ: он может содержать токены и ссылки капчи.
        hints = {
            "bad_authorization": "проверьте HH_APP_TOKEN (токен приложения)",
            "token_expired": "срок действия токена истёк",
            "token_revoked": "токен отозван",
            "application_not_found": "приложение не найдено",
            "user_auth_expected": "данный метод требует авторизации пользователя",
            "captcha_required": "HH требует пройти капчу; автоматические повторы остановлены",
            "bad_user_agent": "HH отклонил заголовок HH-User-Agent",
            "too_many_requests": "достигнут лимит запросов HH",
        }
        known_codes = set(hints) | {
            "oauth", "forbidden", "bad_argument", "bad_arguments", "not_found",
            "unset", "blacklisted", "text", "area", "page", "per_page", "date_from",
        }
        try:
            body = response.json()
        except ValueError:
            body = None
        errors = body.get("errors", []) if isinstance(body, dict) else []
        details = []
        if isinstance(errors, list):
            for error in errors:
                if not isinstance(error, dict):
                    continue
                for key in ("type", "value"):
                    code = error.get(key)
                    if isinstance(code, str) and code in known_codes and code not in details:
                        details.append(code)
        message = f"HH API: HTTP {response.status_code}"
        if details:
            message += "; " + ", ".join(details)
            for code in details:
                if code in hints:
                    message += "; " + hints[code]
        else:
            message += "; ответ без распознаваемого кода HH (возможен отказ шлюза)"
        raise requests.HTTPError(message, response=response)

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
        Поиск вакансий; при наличии используется токен приложения.
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

        r = self.session.get(
            url,
            headers=self._vacancy_headers(),
            params=params,
            timeout=30,
        )
        self._raise_search_error(r)

        data = r.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("HH API: неверный формат списка вакансий")
        return data["items"]

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


