import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import requests

from hh_bump import collect


def settings(**changes):
    values = dict(
        api_base="https://api.hh.ru", app_name="test-app",
        hh_app_token=None,
        search_texts=["Python"], areas=[1], per_page=2,
        max_pages=3, max_searches_per_run=20, days_back=3,
        exclude_keywords=[], exclude_company_keywords=[],
        vacancies_output_file="vacancies.html",
    )
    values.update(changes)
    return SimpleNamespace(**values)


def vacancy(identifier="1", **changes):
    values = dict(
        id=identifier, name="Python developer", employer={"name": "Example"},
        area={"name": "Test"}, alternate_url=f"https://example.com/{identifier}",
        published_at="2026-11-15T10:00:00+00:00",
    )
    values.update(changes)
    return values


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=response)


class CollectVacanciesTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()

    def test_round_robin_gives_each_query_and_area_a_first_page(self):
        s = settings(search_texts=["Python", "SQL", "Python"], areas=[1, 2], max_pages=2)
        self.api.search_vacancies.return_value = [vacancy("1"), vacancy("2")]
        result = collect.collect_vacancies(s, self.api)
        calls = [call.kwargs for call in self.api.search_vacancies.call_args_list]
        self.assertEqual(
            [(call["text"], call["area"], call["page"]) for call in calls],
            [(text, area, page) for page in (0, 1) for text in ("Python", "SQL") for area in (1, 2)],
        )
        self.assertEqual(result.searches_done, 8)
        requested_since = datetime.fromisoformat(calls[0]["date_from"])
        self.assertEqual(requested_since.utcoffset().total_seconds(), 0)
        self.assertLess(abs((datetime.now(timezone.utc) - requested_since).total_seconds() - 3 * 86400), 5)

    def test_full_filtered_page_still_fetches_next_page(self):
        s = settings(exclude_keywords=["senior"])
        self.api.search_vacancies.side_effect = [
            [vacancy("1", name="Senior Python"), vacancy("2", name="SENIOR SQL")],
            [vacancy("3", name="Junior Python")],
        ]
        result = collect.collect_vacancies(s, self.api)
        self.assertEqual(result.searches_done, 2)
        self.assertEqual([v["id"] for v in result.vacancies], ["3"])

    def test_short_page_exhausts_only_its_query(self):
        s = settings(search_texts=["Python", "SQL"], max_pages=3)
        self.api.search_vacancies.side_effect = [
            [vacancy("1")],
            [vacancy("2"), vacancy("3")],
            [],
        ]
        result = collect.collect_vacancies(s, self.api)
        self.assertEqual(
            [(c.kwargs["text"], c.kwargs["page"]) for c in self.api.search_vacancies.call_args_list],
            [("Python", 0), ("SQL", 0), ("SQL", 1)],
        )
        self.assertEqual(result.searches_done, 3)

    def test_failures_count_toward_request_budget(self):
        s = settings(search_texts=["Python", "SQL", "Java"], max_searches_per_run=2)
        self.api.search_vacancies.side_effect = [requests.Timeout("timeout"), []]
        with self.assertLogs(collect.logger, level="ERROR"):
            result = collect.collect_vacancies(s, self.api)
        self.assertEqual(result.searches_done, 2)
        self.assertEqual(result.failed_searches, 1)
        self.assertTrue(result.budget_reached)
        self.assertEqual(self.api.search_vacancies.call_count, 2)

    def test_forbidden_and_rate_limit_stop_all_remaining_searches(self):
        for status in (403, 429):
            with self.subTest(status=status):
                api = Mock()
                api.search_vacancies.side_effect = [
                    [vacancy("1"), vacancy("2")], http_error(status),
                ]
                s = settings(search_texts=["Python", "SQL", "Java"])
                with self.assertLogs(collect.logger, level="ERROR"):
                    result = collect.collect_vacancies(s, api)
                self.assertEqual(api.search_vacancies.call_count, 2)
                self.assertEqual(result.failed_searches, 1)
                self.assertEqual(len(result.vacancies), 2)

    def test_deduplication_keeps_latest_and_sorts_nullable_items(self):
        self.api.search_vacancies.return_value = [
            vacancy("1", published_at="2026-11-13T00:00:00Z"),
            vacancy("2", published_at="2026-11-14T12:00:00+03:00", employer=None, area=None),
            vacancy("1", published_at="2026-11-15T00:00:00", name="Updated"),
            vacancy("3", published_at="not-a-date"),
            vacancy("4", alternate_url=None),
            None,
        ]
        with self.assertLogs(collect.logger, level="WARNING"):
            result = collect.collect_vacancies(settings(per_page=20), self.api)
        self.assertEqual(result.invalid_items, 3)
        self.assertEqual([v["id"] for v in result.vacancies], ["1", "2"])
        self.assertEqual(result.vacancies[0]["name"], "Updated")
        self.assertEqual(result.vacancies[1]["company"], "")
        self.assertEqual(result.vacancies[1]["area"], "")

    def test_company_exclusion_is_case_insensitive(self):
        self.api.search_vacancies.return_value = [
            vacancy("1", employer={"name": "Unwanted LTD"}), vacancy("2"),
        ]
        result = collect.collect_vacancies(
            settings(per_page=20, exclude_company_keywords=["unwanted"]), self.api,
        )
        self.assertEqual([v["id"] for v in result.vacancies], ["2"])

    def test_invalid_configuration_fails_before_requests(self):
        for changes in ({"search_texts": []}, {"areas": []}, {"per_page": 101}, {"max_pages": 0}, {"max_searches_per_run": 0}, {"days_back": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                collect.collect_vacancies(settings(**changes), self.api)
        self.api.search_vacancies.assert_not_called()


class CollectionMainTests(unittest.TestCase):
    def setUp(self):
        # Tests must not append simulated failures to the real Actions summary.
        summary_patch = patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""})
        summary_patch.start()
        self.addCleanup(summary_patch.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / "nested" / "vacancies<&>.json"
        self.settings = settings(vacancies_output_file=str(self.output))
        settings_patch = patch.object(collect, "Settings", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        notifier_patch = patch.object(collect, "TelegramNotifier")
        self.notifier = notifier_patch.start().return_value
        self.addCleanup(notifier_patch.stop)
        api_patch = patch.object(collect, "HHApi")
        self.api_factory = api_patch.start()
        self.addCleanup(api_patch.stop)
        self.api = MagicMock()
        self.api_factory.return_value.__enter__.return_value = self.api
        self.api.search_vacancies.return_value = []

    def test_collects_without_oauth_token_and_escapes_report_and_filename(self):
        self.api.search_vacancies.return_value = [
            vacancy(name='<script>alert("x")</script>', employer={"name": "A & B"}),
        ]
        with patch.dict(os.environ, {}, clear=True):
            collect.main()
        self.api_factory.assert_called_once_with(api_base="https://api.hh.ru", app_name="test-app", token=None)
        report = self.output.with_suffix(".html")
        self.assertTrue(report.exists())
        html = report.read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("A &amp; B", html)
        self.notifier.send.assert_called_once()
        self.assertIn("vacancies&lt;&amp;&gt;.html", self.notifier.send.call_args.args[0])
        self.assertEqual(self.notifier.send.call_args.kwargs["file_path"], report)

    def test_empty_success_notifies_without_failing(self):
        collect.main()
        self.assertIn("не найдены", self.notifier.send.call_args.args[0])
        self.assertNotIn("file_path", self.notifier.send.call_args.kwargs)
        self.assertFalse(self.output.with_suffix(".html").exists())

    def test_complete_search_failure_notifies_and_fails_run(self):
        self.api.search_vacancies.side_effect = requests.Timeout("timeout")
        with self.assertLogs(collect.logger, level="ERROR"), self.assertRaises(RuntimeError):
            collect.main()
        message = self.notifier.send.call_args.args[0]
        self.assertIn("Не удалось собрать", message)
        self.assertNotIn("не найдены", message)
        self.assertNotIn("file_path", self.notifier.send.call_args.kwargs)

    def test_application_token_is_used_for_vacancy_search(self):
        self.settings.hh_app_token = "application-test-token"
        collect.main()
        self.assertEqual(self.api_factory.call_args.kwargs["token"], "application-test-token")

    def test_hh_and_telegram_failures_both_survive_in_ci_summary(self):
        from hh_bump.notifier import TelegramError
        self.api.search_vacancies.side_effect = requests.HTTPError("HH API: HTTP 403; oauth, bad_authorization")
        self.notifier.send.side_effect = TelegramError("Telegram ReadTimeout: результат доставки неизвестен")
        summary = self.output.parent.parent / "summary.md"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
            with self.assertLogs(collect.logger, level="ERROR"), self.assertRaisesRegex(RuntimeError, "Сбой сбора HH"):
                collect.main()
        text = summary.read_text()
        self.assertIn("bad_authorization", text)
        self.assertIn("ReadTimeout", text)

    def test_partial_failure_delivers_available_report_then_fails_run(self):
        self.settings.search_texts = ["Python", "SQL"]
        self.api.search_vacancies.side_effect = [[vacancy()], requests.Timeout("timeout")]
        with self.assertLogs(collect.logger, level="ERROR"), self.assertRaises(RuntimeError):
            collect.main()
        self.assertIn("Подборка неполная", self.notifier.send.call_args.args[0])
        self.assertTrue(self.notifier.send.call_args.kwargs["file_path"].exists())

    def test_invalid_data_does_not_masquerade_as_no_results(self):
        self.api.search_vacancies.return_value = [vacancy(published_at="broken")]
        with self.assertLogs(collect.logger, level="WARNING"), self.assertRaises(RuntimeError):
            collect.main()
        message = self.notifier.send.call_args.args[0]
        self.assertIn("Не удалось собрать", message)
        self.assertIn("некорректных записей: 1", message)

    def test_delivery_failure_propagates(self):
        self.notifier.send.side_effect = RuntimeError("Telegram unavailable")
        with self.assertRaisesRegex(RuntimeError, "Telegram unavailable"):
            collect.main()


if __name__ == "__main__":
    unittest.main()
