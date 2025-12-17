import configparser
from pathlib import Path


import configparser


class Settings:
    def __init__(self, config_path: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding="utf-8")

        # --- HH ---
        hh = self.config["hh"]
        self.api_base = hh.get("api_base")
        self.oauth_token_url = hh.get("oauth_token_url")
        self.app_name = hh.get("app_name")
        self.resume_ids = [
            x.strip() for x in hh.get("resume_ids", "").split(",") if x.strip()
        ]

        # --- SEARCH ---
        apply = self.config["apply"]
        self.search_texts = [
            x.strip() for x in apply.get("search_texts", "").split(",") if x.strip()
        ]
        self.areas = [int(x) for x in apply.get("areas", "").split(",") if x.strip()]
        self.per_page = apply.getint("per_page", 20)
        self.max_pages = apply.getint("max_pages", 5)
        self.max_searches_per_run = apply.getint("max_searches_per_run", 50)

        # --- VACANCY COLLECT ---
        vc = self.config["vacancy_collect"]
        self.vacancies_output_file = vc.get("output_file", "vacancies.csv")
        self.exclude_keywords = [
            x.strip().lower()
            for x in vc.get("exclude_keywords", "").split(",")
            if x.strip()
        ]
        self.days_back = vc.getint("days_back", 3)

        # --- EXCLUDE COMPANIES ---
        vc = self.config["vacancy_collect"]
        self.exclude_company_keywords = [
            x.strip().lower()
            for x in vc.get("exclude_company_keywords", "").splitlines()
            if x.strip()
        ]   

        # --- RESUME ---
        resume = self.config["resume"]
        self.resume_min_interval_minutes = resume.getint(
            "min_interval_minutes", 240
        )

