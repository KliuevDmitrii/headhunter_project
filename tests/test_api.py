import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import requests

from hh_bump.api import HHApi


class HHApiTests(unittest.TestCase):
    def setUp(self):
        self.responses = [(200, {"items": [{"id": "1"}]})]
        self.calls = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.calls.append((self.path, dict(self.headers)))
                status, body = owner.responses.pop(0)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.api = HHApi(f"http://127.0.0.1:{self.server.server_port}", "test-app")
        self.addCleanup(self.api.close)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def search(self):
        return self.api.search_vacancies("QA", 1, 10, 0, "2026-06-01T00:00:00+00:00")

    def test_real_public_request_uses_params_without_token(self):
        self.assertEqual(self.search(), [{"id": "1"}])
        path, headers = self.calls[0]
        self.assertEqual(urlsplit(path).path, "/vacancies")
        self.assertEqual(parse_qs(urlsplit(path).query), {
            "text": ["QA"], "area": ["1"], "per_page": ["10"], "page": ["0"],
            "date_from": ["2026-06-01T00:00:00+00:00"],
        })
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["HH-User-Agent"], "test-app")

    def test_transient_failure_retries_and_recovers(self):
        self.responses.insert(0, (503, {}))
        self.assertEqual(self.search(), [{"id": "1"}])
        self.assertEqual(len(self.calls), 2)

    def test_application_authorization_reaches_hh(self):
        self.api.token = "test-application-token"
        self.search()
        self.assertEqual(self.calls[0][1]["Authorization"], "Bearer test-application-token")

    def test_forbidden_explains_auth_failure_without_dumping_body(self):
        self.responses = [(403, {"errors": [
            {"type": "oauth", "value": "bad_authorization"},
        ], "access_token": "secret-token", "description": "secret-token"})]
        with self.assertRaises(requests.HTTPError) as error:
            self.search()
        message = str(error.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("bad_authorization", message)
        self.assertIn("HH_APP_TOKEN", message)
        self.assertNotIn("secret-token", message)
        self.assertEqual(error.exception.response.status_code, 403)

    def test_captcha_error_excludes_challenge_url(self):
        self.responses = [(403, {"errors": [{
            "type": "captcha_required", "value": "captcha_required",
            "captcha_url": "https://example.com/captcha?state=private-challenge",
        }]})]
        with self.assertRaises(requests.HTTPError) as error:
            self.search()
        self.assertIn("captcha_required", str(error.exception))
        self.assertNotIn("private-challenge", str(error.exception))

    def test_unrecognized_error_does_not_expose_response(self):
        self.responses = [(403, {"errors": [{"type": "secret-type", "value": "secret-value"}]})]
        with self.assertRaises(requests.HTTPError) as error:
            self.search()
        self.assertIn("без распознаваемого кода", str(error.exception))
        self.assertNotIn("secret-", str(error.exception))

    def test_persistent_failure_has_bounded_retries(self):
        self.responses = [(503, {})] * 3
        with patch("urllib3.util.retry.time.sleep"), self.assertRaises(requests.exceptions.RetryError):
            self.search()
        self.assertEqual(len(self.calls), 3)

    def test_client_errors_are_not_retried(self):
        for status in (400, 403, 429):
            with self.subTest(status=status):
                self.responses = [(status, {})]
                previous = len(self.calls)
                with self.assertRaises(requests.HTTPError) as error:
                    self.search()
                self.assertEqual(error.exception.response.status_code, status)
                self.assertEqual(len(self.calls) - previous, 1)

    def test_invalid_response_is_not_treated_as_empty_search(self):
        for body in ({}, {"items": None}, {"items": {}}, []):
            with self.subTest(body=body):
                self.responses = [(200, body)]
                with self.assertRaisesRegex(ValueError, "формат"):
                    self.search()


if __name__ == "__main__":
    unittest.main()
