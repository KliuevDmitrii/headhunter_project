import os
import configparser
from pathlib import Path


class Settings:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read("config.ini")

        # --- HH ---
        hh = config["hh"]
        self.api_base = hh.get("api_base")
        self.oauth_token_url = hh.get("oauth_token_url")

        # --- APPLY (используем только для поиска, БЕЗ автоотклика) ---
        apply = config["apply"]
        self.search_texts = [
            t.strip() for t in apply.get("search_texts", "").split(",") if t.strip()
        ]
        self.areas = [
            int(a.strip()) for a in apply.get("areas", "").split(",") if a.strip()
        ]
        self.per_page = apply.getint("per_page", fallback=20)
        self.max_pages = apply.getint("max_pages", fallback=5)
        self.max_searches_per_run = apply.getint("max_searches_per_run", fallback=50)

        # --- VACANCY COLLECT ---
        vc = config["vacancy_collect"]
        self.vacancies_output_file = vc.get("output_file", "vacancies.csv")

        # --- RUN ---
        run = config["run"]
        self.min_interval_minutes = run.getint("min_interval_minutes", fallback=0)

        # --- RESUME (оставляем на будущее, но collect его не использует) ---
        resume = config["resume"]
        self.resume_min_interval_minutes = resume.getint(
            "min_interval_minutes", fallback=240
        )


