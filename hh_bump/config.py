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

        # Apply (отклики)
        apply = self.config["apply"] if "apply" in self.config else {}
        self.apply_texts = [
            t.strip()
            for t in apply.get("search_texts", "").split(",")
            if t.strip()
        ]
        self.apply_areas = [
            int(a.strip())
            for a in apply.get("areas", "").split(",")
            if a.strip().isdigit()
        ]
        self.apply_per_page = apply.getint("per_page", 5)
        self.cover_letters = [
            c.strip()
            for c in apply.get("cover_letters", "").split(",")
            if c.strip()
        ]
        self.max_applications_per_run = apply.getint("max_applications_per_run", 10)
        self.sleep_between_applies = apply.getint("sleep_between_applies", 2)



