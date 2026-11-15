import tempfile
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from hh_bump.notifier import TelegramError, TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    token = "123456:secret-bot-token"

    def setUp(self):
        self.settings = SimpleNamespace(tg_bot_token=self.token, tg_chat_id="42")
        settings_patch = patch("hh_bump.config.Settings", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        post_patch = patch("hh_bump.notifier.requests.post")
        self.post = post_patch.start()
        self.addCleanup(post_patch.stop)
        self.post.return_value = Mock(status_code=200)
        self.post.return_value.json.return_value = {"ok": True, "result": {}}

    def test_text_delivery_has_finite_timeout(self):
        TelegramNotifier().send("Test")
        self.assertEqual(self.post.call_count, 1)
        self.assertTrue(self.post.call_args.args[0].endswith("/sendMessage"))
        self.assertEqual(self.post.call_args.kwargs["timeout"], (10, 60))
        self.assertEqual(self.post.call_args.kwargs["json"]["chat_id"], "42")

    def test_report_is_one_document_with_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "vacancies.html"
            report.write_text("<html>Report</html>")
            uploaded = []
            response = self.post.return_value

            def receive(*args, **kwargs):
                uploaded.append(kwargs["files"]["document"].read())
                return response

            self.post.side_effect = receive
            TelegramNotifier().send("<b>Report</b>", report)
        self.assertEqual(self.post.call_count, 1)
        self.assertTrue(self.post.call_args.args[0].endswith("/sendDocument"))
        self.assertEqual(self.post.call_args.kwargs["data"]["caption"], "<b>Report</b>")
        self.assertEqual(uploaded, [b"<html>Report</html>"])

    def test_long_caption_is_sent_as_separate_text(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            report.write_text("Report")
            TelegramNotifier().send("x" * 1025, report)
        self.assertEqual(self.post.call_count, 2)
        self.assertTrue(self.post.call_args_list[0].args[0].endswith("/sendMessage"))
        self.assertNotIn("caption", self.post.call_args.kwargs["data"])

    def test_missing_report_does_not_send_notification(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                TelegramNotifier().send("Report", Path(directory) / "missing.html")
        self.post.assert_not_called()

    def test_missing_variable_is_named(self):
        self.settings.tg_bot_token = "  "
        with self.assertRaisesRegex(TelegramError, "TG_BOT_TOKEN") as error:
            TelegramNotifier()
        self.assertNotIn("TG_CHAT_ID", str(error.exception))

    def test_http_error_has_description_without_token(self):
        self.post.return_value.status_code = 403
        self.post.return_value.json.return_value = {
            "ok": False,
            "description": f"Forbidden: bot was blocked {self.token}, chat {self.settings.tg_chat_id}",
        }
        with self.assertRaises(TelegramError) as error:
            TelegramNotifier().send("Test")
        self.assertIn("bot was blocked", str(error.exception))
        self.assertIn("HTTP 403", str(error.exception))
        self.assertNotIn(self.token, str(error.exception))
        self.assertNotIn(self.settings.tg_chat_id, str(error.exception))

    def test_document_error_is_reported_without_success_notification(self):
        self.post.return_value.status_code = 400
        self.post.return_value.json.return_value = {
            "ok": False, "description": "Bad Request: chat not found"
        }
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            report.write_text("Report")
            with self.assertRaisesRegex(TelegramError, "sendDocument.*chat not found"):
                TelegramNotifier().send("Report", report)
        self.post.assert_called_once()

    def test_json_failure_on_http_200_is_not_success(self):
        self.post.return_value.json.return_value = {
            "ok": False, "description": "Bad Request: chat not found"
        }
        with self.assertRaisesRegex(TelegramError, "chat not found"):
            TelegramNotifier().send("Test")

    def test_invalid_json_is_delivery_error(self):
        self.post.return_value.json.side_effect = ValueError("not JSON")
        with self.assertRaisesRegex(TelegramError, "некорректный ответ API"):
            TelegramNotifier().send("Test")

    def test_rate_limit_explains_when_to_retry(self):
        self.post.return_value.status_code = 429
        self.post.return_value.json.return_value = {
            "ok": False, "description": "Too Many Requests",
            "parameters": {"retry_after": 15},
        }
        with self.assertRaisesRegex(TelegramError, "15 с"):
            TelegramNotifier().send("Test")
        self.post.assert_called_once()

    def test_timeout_does_not_retry_or_leak_token(self):
        self.post.side_effect = requests.Timeout(f"URL: /bot{self.token}/sendMessage")
        try:
            TelegramNotifier().send("Test")
        except TelegramError:
            rendered = traceback.format_exc()
        else:
            self.fail("Expected delivery error")
        self.assertIn("результат доставки неизвестен", rendered)
        self.assertNotIn(self.token, rendered)
        self.post.assert_called_once()

    def test_connection_error_does_not_leak_token(self):
        self.post.side_effect = requests.ConnectionError(f"URL /bot{self.token}")
        try:
            TelegramNotifier().send("Test")
        except TelegramError:
            rendered = traceback.format_exc()
        else:
            self.fail("Expected delivery error")
        self.assertNotIn(self.token, rendered)
        self.assertIn("api.telegram.org", rendered)


if __name__ == "__main__":
    unittest.main()
