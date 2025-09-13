import requests


def refresh_access_token(
        oauth_token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str) -> str:
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    r = requests.post(oauth_token_url, data=data, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]
