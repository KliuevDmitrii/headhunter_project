import os
import configparser
from dotenv import load_dotenv
from pathlib import Path


class Settings:
    def __init__(self, cfg_path: str = "config.ini"):
        load_dotenv()  # .env локально; на CI используем Secrets
        self.config = configparser.ConfigParser()
        self.config.read(cfg_path)

        # HH API
        hh = self.config["hh"]
        self.api_base = hh.get("api_base", "https://api.hh.ru")
        self.oauth_token_url = hh.get("oauth_token_url",
                                      "https://hh.ru/oauth/token"
                                      )
        raw_ids = hh.get("resume_ids", "").strip()
        self.resume_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]

        # Secrets из окружения
        self.client_id = os.environ["HH_CLIENT_ID"]
        self.client_secret = os.environ["HH_CLIENT_SECRET"]
        self.refresh_token = os.environ["HH_REFRESH_TOKEN"]

        # Run
        run = self.config["run"]
        self.min_interval_minutes = run.getint("min_interval_minutes", 0)

        # State file
        self.state_path = Path("state.json")
