from config import Settings
from auth import refresh_access_token


s = Settings()

token = refresh_access_token(
    oauth_token_url=s.oauth_token_url,
    client_id=s.client_id,
    client_secret=s.client_secret,
    refresh_token=s.refresh_token,
)

print("✅ Новый access_token:", token)
