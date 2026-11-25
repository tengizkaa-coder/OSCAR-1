#!/usr/bin/env python3
"""Локальный сервер для просмотра сайта.

Отличие от `python3 -m http.server`: запрос «/» перенаправляется на «/test/»,
потому что рабочие страницы по задумке закрыты белым экраном для компьютеров.
Сам сайт при этом не меняется — это только удобство локального просмотра.

Запуск: python3 tools/preview-server.py [порт]   (по умолчанию 8000)
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            self.send_response(302)
            self.send_header("Location", "/test/")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Просмотр: http://0.0.0.0:{port}/test/  (корень «/» ведёт на /test/)")
    server.serve_forever()


if __name__ == "__main__":
    main()
