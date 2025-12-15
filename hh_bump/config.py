import configparser


class Settings:
    def __init__(self, cfg_path: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(cfg_path)

        # ---------- HH ----------
        hh = self.config["hh"]
        self.api_base = hh.get("api_base", "https://api.hh.ru")
        self.oauth_token_url = hh.get("oauth_token_url")

        # ---------- Search (используется collect.py) ----------
        apply = self.config["apply"]

        self.apply_search_texts = [
            x.strip()
            for x in apply.get("search_texts", "").split(",")
            if x.strip()
        ]

        self.apply_areas = [
            int(x.strip())
            for x in apply.get("areas", "").split(",")
            if x.strip()
        ]

        self.apply_per_page = apply.getint("per_page", 20)
        self.apply_max_pages = apply.getint("max_pages", 5)
        self.max_searches_per_run = apply.getint("max_searches_per_run", 50)

        # ---------- Vacancy collect ----------
        collect = self.config["vacancy_collect"]
        self.vacancies_output_file = collect.get(
            "output_file", "vacancies.csv"
        )


