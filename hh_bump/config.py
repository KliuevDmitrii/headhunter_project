# hh_bump/config.py
import os
import configparser
from pathlib import Path
from dotenv import load_dotenv


class Settings:
    def __init__(self, cfg_path: str = "config.ini"):
        load_dotenv()  # локально .env; на GitHub Actions Secrets

        # 1) Ищем config.ini (CWD или корень проекта)
        cfg_file = Path(cfg_path)
        if not cfg_file.exists():
            # корень проекта: .../headhunter_project/config.ini
            project_root = Path(__file__).resolve().parents[1]
            alt = project_root / cfg_path
            if alt.exists():
                cfg_file = alt

        if not cfg_file.exists():
            raise RuntimeError(
                f"❌ Не найден файл конфигурации: {cfg_path} "
                f"(пробовал также рядом с проектом)."
            )

        self.config = configparser.ConfigParser()
        self.config.read(cfg_file, encoding="utf-8")

        # ---------- HH ----------
        if "hh" not in self.config:
            raise RuntimeError("❌ В config.ini отсутствует секция [hh]")

        hh = self.config["hh"]
        self.api_base = hh.get("api_base", "https://api.hh.ru").rstrip("/")
        self.oauth_token_url = hh.get("oauth_token_url", "https://hh.ru/oauth/token").rstrip("/")

        raw_ids = hh.get("resume_ids", "")
        # Важно: у тебя сейчас resume_ids — это HASH'и резюме (как в ответах HH),
        # мы их просто храним списком строк.
        self.resume_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
        if not self.resume_ids:
            raise RuntimeError("❌ В [hh] пустой resume_ids")

        # ---------- Secrets (env) ----------
        self.client_id = os.getenv("HH_CLIENT_ID")
        self.client_secret = os.getenv("HH_CLIENT_SECRET")
        self.refresh_token = os.getenv("HH_REFRESH_TOKEN")

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise RuntimeError("❌ Не заданы HH_CLIENT_ID / HH_CLIENT_SECRET / HH_REFRESH_TOKEN")

        # ---------- Run (опционально) ----------
        run_cfg = self.config["run"] if "run" in self.config else {}
        self.run_min_interval_minutes = int(run_cfg.get("min_interval_minutes", 0))

        # ---------- Resume (поднятие) ----------
        resume_cfg = self.config["resume"] if "resume" in self.config else {}
        self.resume_min_interval_minutes = int(resume_cfg.get("min_interval_minutes", 240))

        # ---------- Collect вакансий (настройки поиска) ----------
        # (оставляем секцию [apply], но это НЕ автоотклик — только параметры поиска)
        if "apply" not in self.config:
            raise RuntimeError("❌ В config.ini отсутствует секция [apply] (нужна для сбора вакансий)")

        apply_cfg = self.config["apply"]

        raw_texts = apply_cfg.get("search_texts", "")
        self.search_texts = [x.strip() for x in raw_texts.split(",") if x.strip()]
        if not self.search_texts:
            raise RuntimeError("❌ В [apply] пустой search_texts")

        raw_areas = apply_cfg.get("areas", "")
        self.areas = [int(x.strip()) for x in raw_areas.split(",") if x.strip()]
        if not self.areas:
            raise RuntimeError("❌ В [apply] пустой areas")

        self.per_page = int(apply_cfg.get("per_page", 20))
        self.max_pages = int(apply_cfg.get("max_pages", 5))
        self.max_searches_per_run = int(apply_cfg.get("max_searches_per_run", 50))

        # ---------- Output для collect ----------
        collect_cfg = self.config["vacancy_collect"] if "vacancy_collect" in self.config else {}
        self.vacancies_output_file = collect_cfg.get("output_file", "vacancies.json")

        # ---------- State ----------
        # state.json храним в корне проекта (рядом с config.ini)
        self.project_root = Path(__file__).resolve().parents[1]
        self.state_path = self.project_root / "state.json"

