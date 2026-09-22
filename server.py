from __future__ import annotations

import argparse
import errno
import json
import mimetypes
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from installer import core


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
ACTION_LOCK = threading.Lock()
ACTION_STATE_LOCK = threading.Lock()
ACTION_STATE: dict[str, dict] = {}


def _set_action(action_id: str, phase: str, progress: int | None, message: str, **extra) -> None:
    with ACTION_STATE_LOCK:
        ACTION_STATE[action_id] = {
            "id": action_id,
            "phase": phase,
            "progress": progress,
            "message": message,
            "updatedAt": time.time(),
            **extra,
        }
        if len(ACTION_STATE) > 24:
            oldest = sorted(ACTION_STATE, key=lambda key: ACTION_STATE[key]["updatedAt"])[:-24]
            for key in oldest:
                ACTION_STATE.pop(key, None)


def _get_action(action_id: str | None) -> dict | None:
    if not action_id:
        return None
    with ACTION_STATE_LOCK:
        value = ACTION_STATE.get(action_id)
        return dict(value) if value else None


class Handler(BaseHTTPRequestHandler):
    server_version = "KoboVietnameseInstaller/1.0"

    def log_message(self, format_string: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        if self.headers.get("X-Kobo-Installer") != "1":
            raise core.InstallerError("Invalid local request.")
        if self.headers.get_content_type() != "application/json":
            raise core.InstallerError("Expected a JSON request.")
        length = int(self.headers.get("Content-Length", "0"))
        if length > 32 * 1024 * 1024:
            raise core.InstallerError("Request is too large.")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            selected = parse_qs(parsed.query).get("device", [None])[0]
            self._json(HTTPStatus.OK, {"ok": True, "status": core.device_status(selected)})
            return
        if parsed.path == "/api/action-status":
            action_id = parse_qs(parsed.query).get("id", [None])[0]
            action = _get_action(action_id)
            if action is None:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Action not found."})
            else:
                self._json(HTTPStatus.OK, {"ok": True, "action": action})
            return
        relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
        target = (WEB / relative).resolve()
        try:
            target.relative_to(WEB.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        action_id = self.headers.get("X-Kobo-Action") or uuid.uuid4().hex
        _set_action(action_id, "queued", 0, "Waiting for the installer to start…")
        try:
            body = self._read_json()
            if not ACTION_LOCK.acquire(blocking=False):
                raise core.InstallerError("Another installer action is already running.")
            try:
                def progress(phase: str, percent: int | None, message: str, **_details) -> None:
                    _set_action(action_id, phase, percent, message)

                _set_action(action_id, "starting", 2, "Starting the requested action…")
                if self.path == "/api/build":
                    result = core.build_font_package(progress=progress)
                elif self.path == "/api/repair-upload":
                    result = core.repair_uploaded_nickelmenu(
                        body.get("filename", ""), body.get("archiveBase64", ""), body.get("version", "")
                    )
                elif self.path == "/api/repair-koboroot-upload":
                    result = core.repair_uploaded_koboroot(
                        body.get("filename", ""), body.get("archiveBase64", ""), body.get("version", "")
                    )
                elif self.path == "/api/install":
                    components = body.get("components")
                    if not isinstance(components, list):
                        raise core.InstallerError("components must be a list.")
                    result = core.install_selected(components, body.get("devicePath"), progress=progress)
                elif self.path == "/api/eject":
                    result = core.safely_eject(body.get("devicePath"))
                elif self.path == "/api/open-folder":
                    result = core.open_device_folder(body.get("devicePath"))
                elif self.path == "/api/choose-folder":
                    result = core.choose_device_folder()
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Unknown action."})
                    return
            finally:
                ACTION_LOCK.release()
            _set_action(action_id, "complete", 100, result.get("message", "The action completed successfully."))
            self._json(HTTPStatus.OK, {"ok": True, "actionId": action_id, "result": result, "status": core.device_status(body.get("devicePath"))})
        except (core.InstallerError, json.JSONDecodeError, ValueError) as exc:
            _set_action(action_id, "error", None, str(exc))
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "actionId": action_id, "error": str(exc), "status": core.device_status(body.get("devicePath") if "body" in locals() else None)})
        except Exception as exc:
            message = f"Unexpected error: {exc}"
            _set_action(action_id, "error", None, message)
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "actionId": action_id, "error": message})


def _bind_server(host: str, port: int, attempts: int = 20) -> ThreadingHTTPServer:
    last_error: OSError | None = None
    for candidate in range(port, port + attempts):
        try:
            return ThreadingHTTPServer((host, candidate), Handler)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
            last_error = exc
    raise SystemExit(
        f"No free port found between {port} and {port + attempts - 1}. "
        f"Close whatever is using them and try again. ({last_error})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Kobo Vietnamese Installer web interface.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("For safety, this installer only binds to localhost.")
    server = _bind_server(args.host, args.port)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    if port != args.port:
        print(f"Port {args.port} is in use; using {port} instead.")
    print(f"Kobo Vietnamese Installer running at {url}")
    print("Press Control-C to stop.")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
