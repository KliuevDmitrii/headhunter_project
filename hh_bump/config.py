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

        # Apply (отклики на вакансии)
        apply = self.config["apply"]

        raw_texts = apply.get("search_texts", "").strip()
        self.apply_search_texts = [x.strip() for x in raw_texts.split(",") if x.strip()]

        raw_areas = apply.get("areas", "").strip()
        self.apply_areas = [int(x.strip()) for x in raw_areas.split(",") if x.strip()]

        self.apply_per_page = apply.getint("per_page", 20)
        self.apply_max_pages = apply.getint("max_pages", 1)

        self.max_applications_per_run = apply.getint("max_applications_per_run", 10)
        self.sleep_between_applies = apply.getint("sleep_between_applies", 2)
        self.max_searches_per_run = apply.getint("max_searches_per_run", 30)

        raw_covers = apply.get("cover_letters", "").strip()
        self.cover_letters = [x.strip() for x in raw_covers.split(",") if x.strip()]
        
