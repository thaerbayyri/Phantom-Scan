from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import Callable

from .runtime import PhantomRuntime


class RuntimeApiServer:
    def __init__(self, runtime: PhantomRuntime, host: str = "127.0.0.1", port: int = 8789) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/api/health":
                    self._json(HTTPStatus.OK, {"status": "ok", "runtime_mode": runtime.current_mode().value})
                    return
                if self.path == "/api/status":
                    self._json(HTTPStatus.OK, runtime.status())
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path == "/api/control/start":
                    runtime.start_session()
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if self.path == "/api/control/stop":
                    runtime.stop_session()
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def log_message(self, format: str, *args: object) -> None:
                return

            def _json(self, status: HTTPStatus, payload: dict) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status.value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
