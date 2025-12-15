import os
import requests
import json
from pathlib import Path
from hh_bump.config import Settings

STATE_FILE = Path("state.json")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_stored_access_token():
    """
    Берём access_token из state.json
    или из переменной окружения HH_ACCESS_TOKEN
    """
    state = load_state()
    token = state.get("access_token") or os.getenv("HH_ACCESS_TOKEN")
    return token


def store_access_token(token: str):
    """Сохраняем access_token в state.json"""
    state = load_state()
    state["access_token"] = token
    save_state(state)


def refresh_access_token(
        oauth_token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str) -> str:
    """Запрашиваем новый access_token через refresh_token"""
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    r = requests.post(oauth_token_url, data=data, timeout=30)
    r.raise_for_status()
    token = r.json()["access_token"]
    store_access_token(token)
    return token

def get_valid_access_token() -> str:
    """
    Возвращает рабочий access_token.
    Если текущий истёк или отсутствует — обновляет через refresh_token.
    """
    s = Settings()

    token = get_stored_access_token()

    if token:
        # проверяем токен через /me
        resp = requests.get(
            f"{s.api_base}/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return token

        if resp.status_code != 401:
            # 403 и прочее — считаем токен битым
            token = None

    # если токена нет или он протух
    token = refresh_access_token(
        s.oauth_token_url,
        s.client_id,
        s.client_secret,
        s.refresh_token,
    )

    return token
