import argparse
import itertools
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _normalize_backend(url):
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    if not url.endswith("/"):
        url += "/"
    return url


class RoundRobinPicker:
    def __init__(self, backends):
        self._cycle = itertools.cycle(backends)
        self._lock = threading.Lock()

    def next(self):
        with self._lock:
            return next(self._cycle)


class RequestCounter:
    def __init__(self, backends):
        self._lock = threading.Lock()
        self._counts = {urlsplit(backend).netloc: 0 for backend in backends}
        self._total = 0

    def record(self, upstream_host):
        with self._lock:
            self._counts.setdefault(upstream_host, 0)
            self._counts[upstream_host] += 1
            self._total += 1
            return {
                "total_requests": self._total,
                "per_upstream": dict(self._counts),
            }

    def snapshot(self):
        with self._lock:
            return {
                "total_requests": self._total,
                "per_upstream": dict(self._counts),
            }


class LoadBalancerHandler(BaseHTTPRequestHandler):
    server_version = "py-lb/1.0"

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def log_request(self, code="-", size="-"):
        # Suppress BaseHTTPRequestHandler's default access log so we can emit a
        # clearer upstream-aware line after each proxied request completes.
        return

    def _read_body(self):
        length = self.headers.get("Content-Length")
        if not length:
            return b""
        try:
            length = int(length)
        except ValueError:
            return b""
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _send_json_response(self, status_code, payload):
        response_body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _log_upstream_result(self, status_code, upstream_host, duration_ms):
        self.log_message(
            '"%s" %s upstream=%s duration_ms=%.2f',
            self.requestline,
            status_code,
            upstream_host,
            duration_ms,
        )

    def _write_proxy_response(self, status_code, response_headers, response_body, upstream_host):
        stats = self.server.request_counter.record(upstream_host)
        content_type = response_headers.get("Content-Type", "")
        body_to_send = response_body

        if "application/json" in content_type.lower():
            try:
                parsed_body = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed_body = None
            if isinstance(parsed_body, dict):
                parsed_body["load_balancer"] = {
                    "current_upstream": upstream_host,
                    "request_counts": stats["per_upstream"],
                    "total_requests": stats["total_requests"],
                }
                body_to_send = json.dumps(parsed_body).encode("utf-8")

        self.send_response(status_code)
        for key, value in response_headers.items():
            if key.lower() in HOP_BY_HOP_HEADERS or key.lower() == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body_to_send)))
        self.send_header("X-Upstream", upstream_host)
        self.send_header("X-Total-Requests", str(stats["total_requests"]))
        self.send_header("X-Upstream-Count", str(stats["per_upstream"].get(upstream_host, 0)))
        self.send_header("X-Upstream-Counts", json.dumps(stats["per_upstream"], separators=(",", ":")))
        self.end_headers()
        self.wfile.write(body_to_send)

    def _proxy(self):
        started_at = time.perf_counter()
        if self.command == "GET" and self.path == "/_lb/stats":
            self._send_json_response(
                200,
                {
                    "success": True,
                    "message": "Load balancer stats loaded.",
                    "data": self.server.request_counter.snapshot(),
                },
            )
            self._log_upstream_result(200, "load-balancer", (time.perf_counter() - started_at) * 1000)
            return

        body = self._read_body()
        attempts = 0
        last_error = None

        while attempts < self.server.max_attempts:
            attempts += 1
            backend = self.server.picker.next()
            upstream_url = urljoin(backend, self.path.lstrip("/"))
            upstream_host = urlsplit(backend).netloc

            headers = {}
            for key, value in self.headers.items():
                if key.lower() in HOP_BY_HOP_HEADERS:
                    continue
                if key.lower() == "host":
                    continue
                headers[key] = value
            headers["Host"] = upstream_host
            headers["X-Forwarded-For"] = self.client_address[0]
            headers["X-Forwarded-Proto"] = "http"

            request = Request(upstream_url, data=body if body else None, headers=headers, method=self.command)
            try:
                with urlopen(request, timeout=self.server.upstream_timeout_seconds) as response:
                    response_body = response.read()
                    self._write_proxy_response(response.status, response.headers, response_body, upstream_host)
                    self._log_upstream_result(response.status, upstream_host, (time.perf_counter() - started_at) * 1000)
                    return
            except HTTPError as exc:
                response_body = exc.read() if getattr(exc, "fp", None) is not None else b""
                self._write_proxy_response(exc.code, exc.headers, response_body, upstream_host)
                self._log_upstream_result(exc.code, upstream_host, (time.perf_counter() - started_at) * 1000)
                return
            except (URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_error = (backend, exc)
                continue

        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        backend, exc = last_error if last_error else ("", Exception("No backends available"))
        self.wfile.write(
            (
                '{"success":false,"message":"Bad gateway: upstream unavailable.","code":"BAD_GATEWAY","errors":{"upstream":"%s","detail":"%s"}}'
                % (str(backend).replace('"', '\\"'), str(exc).replace('"', '\\"'))
            ).encode("utf-8")
        )
        self._log_upstream_result(502, urlsplit(backend).netloc if backend else "unavailable", (time.perf_counter() - started_at) * 1000)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8000)
    parser.add_argument(
        "--backends",
        required=True,
        help="Comma-separated upstream base URLs, e.g. http://127.0.0.1:8001,http://127.0.0.1:8002",
    )
    parser.add_argument("--upstream-timeout", type=float, default=15.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    return parser.parse_args()


def main():
    args = parse_args()
    backends = [_normalize_backend(value) for value in args.backends.split(",")]
    backends = [value for value in backends if value]
    if not backends:
        raise SystemExit("No valid backends provided.")

    server = ThreadingHTTPServer((args.listen_host, args.listen_port), LoadBalancerHandler)
    server.picker = RoundRobinPicker(backends)
    server.request_counter = RequestCounter(backends)
    server.upstream_timeout_seconds = args.upstream_timeout
    server.max_attempts = max(1, args.max_attempts)

    print(f"Load balancer listening on http://{args.listen_host}:{args.listen_port}")
    print("Backends:")
    for value in backends:
        print(f"- {value}")
    server.serve_forever()


if __name__ == "__main__":
    main()

