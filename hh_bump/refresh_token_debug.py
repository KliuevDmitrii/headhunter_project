import os
import sys
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==== Настройка: укажи свои client_id и client_secret ====
CLIENT_ID = os.getenv("HH_CLIENT_ID") or "NQE4N7H3UJKUGSR4V9LS49L0LUE89S9S3IK8VCP1JLMBLSBRI38IUHTINFQJILNI"
CLIENT_SECRET = os.getenv("HH_CLIENT_SECRET") or "QS1A1GV10TKN2ACKRUE688D09I5CGO78KE2TFRTT090OOAFSR4DM2NRTOBEISAGF"
REDIRECT_URI = "http://localhost:53682/callback"

# простой HTTP-сервер для приёма кода
class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        code = params.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code in callback URL")
            return

        # сразу меняем code на токены
        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }
        r = requests.post("https://hh.ru/oauth/token", data=data, timeout=30)
        r.raise_for_status()
        tokens = r.json()

        # печатаем в консоль
        print("\n=== TOKENS RECEIVED ===")
        print("access_token:", tokens.get("access_token"))
        print("refresh_token:", tokens.get("refresh_token"))
        print("expires_in:", tokens.get("expires_in"))
        print("=======================")

        # ответ в браузере
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"You can close this tab. Refresh token printed in console.")

        # завершаем сервер
        sys.exit(0)


def main():
    # запускаем локальный сервер
    server = HTTPServer(("localhost", 53682), OAuthHandler)

    # открываем браузер для авторизации
    auth_url = (
        f"https://hh.ru/oauth/authorize?response_type=code"
        f"&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    print("Откроется окно браузера для входа на hh.ru:")
    print(auth_url)
    webbrowser.open(auth_url)

    # ждём запрос от hh с code
    server.serve_forever()


if __name__ == "__main__":
    main()

