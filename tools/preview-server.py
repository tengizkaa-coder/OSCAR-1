#!/usr/bin/env python3
"""Локальный сервер для просмотра сайта.

Отдаёт собранный сайт как есть: «/» — рабочая главная, «/test/» — тестовое дерево.
Слушает 0.0.0.0, чтобы страница открывалась и по внешнему адресу песочницы.

Запуск: python3 tools/preview-server.py [порт]   (по умолчанию 8000)
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        # Локальный просмотр не должен кэшировать сборку.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Просмотр: http://0.0.0.0:{port}/   (тестовое дерево — /test/)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
