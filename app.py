#!/usr/bin/env python3
import json
import hmac
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("PROBE_CONFIG", APP_DIR / "config.json"))
STATIC_DIR = APP_DIR / "static"

STATE_LOCK = threading.Lock()
STATE = {
    "started_at": int(time.time() * 1000),
    "results": {},
    "targets": [],
}


def now_ms():
    return int(time.time() * 1000)


def load_config():
    defaults = {
        "node_id": "local",
        "node_name": socket.gethostname(),
        "location": "local",
        "bind_host": "0.0.0.0",
        "port": 8099,
        "admin_token": "",
        "interval_seconds": 5,
        "history_minutes": 60,
        "targets": [
            {
                "id": "cloudflare-dns",
                "name": "Cloudflare DNS",
                "kind": "icmp",
                "host": "1.1.1.1",
            },
            {
                "id": "google-dns",
                "name": "Google DNS",
                "kind": "icmp",
                "host": "8.8.8.8",
            },
        ],
        "remote_nodes": [],
    }
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            user_config = json.load(f)
        defaults.update(user_config)
    return defaults


def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp_path.replace(CONFIG_PATH)


def public_config(config):
    safe = {
        "node_id": config.get("node_id", "local"),
        "node_name": config.get("node_name", socket.gethostname()),
        "location": config.get("location", ""),
        "port": config.get("port", 8099),
        "interval_seconds": config.get("interval_seconds", 5),
        "history_minutes": config.get("history_minutes", 60),
        "targets": sanitize_targets(config.get("targets", [])),
        "remote_nodes": [],
        "admin_enabled": bool(config.get("admin_token")),
    }
    for node in config.get("remote_nodes", []):
        item = dict(node)
        item.pop("admin_token", None)
        item.pop("token", None)
        safe["remote_nodes"].append(item)
    return safe


def target_id(target):
    raw = target.get("id") or target.get("name") or target.get("host") or target.get("url")
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw).strip().lower()).strip("-") or "target"


def sanitize_targets(targets):
    clean = []
    for target in targets:
        item = dict(target)
        item["id"] = target_id(item)
        item.setdefault("name", item["id"])
        item.setdefault("kind", "icmp")
        clean.append(item)
    return clean


def validate_remote_node(node):
    item = dict(node)
    url = str(item.get("url", "")).strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("VPS URL must start with http:// or https://")
    item["url"] = url
    item["id"] = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "-",
        str(item.get("id") or item.get("name") or parsed.netloc).lower(),
    ).strip("-")
    if not item["id"]:
        raise ValueError("VPS ID is required")
    item["name"] = str(item.get("name") or item["id"]).strip()
    item["location"] = str(item.get("location") or "").strip()
    token = str(item.get("admin_token") or item.get("token") or "").strip()
    if token:
        item["admin_token"] = token
    item.pop("token", None)
    return item


def validate_target(target):
    item = dict(target)
    item["kind"] = str(item.get("kind", "icmp")).lower()
    if item["kind"] not in ("icmp", "http", "tcp"):
        raise ValueError("target kind must be icmp, http, or tcp")
    item["id"] = target_id(item)
    item["name"] = str(item.get("name") or item["id"]).strip()
    item["timeout_seconds"] = float(item.get("timeout_seconds", 3))
    if item["kind"] == "http":
        url = str(item.get("url", "")).strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("HTTP target URL must start with http:// or https://")
        item["url"] = url
        item.pop("host", None)
        item.pop("port", None)
    elif item["kind"] == "tcp":
        host = str(item.get("host", "")).strip()
        port = int(item.get("port", 0))
        if not host or port < 1 or port > 65535:
            raise ValueError("TCP target requires host and valid port")
        item["host"] = host
        item["port"] = port
        item.pop("url", None)
    else:
        host = str(item.get("host", "")).strip()
        if not host:
            raise ValueError("ICMP target requires host")
        item["host"] = host
        item.pop("url", None)
        item.pop("port", None)
    return item


def upsert_by_id(items, item):
    result = [old for old in items if old.get("id") != item.get("id")]
    result.append(item)
    return result


def sync_target_to_remote_nodes(config, target):
    synced = []
    skipped = []
    payload = json.dumps(
        {
            "admin_token": "",
            "target": target,
            "sync": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    for node in config.get("remote_nodes", []):
        token = node.get("admin_token") or ""
        if not token:
            skipped.append({"id": node.get("id"), "reason": "missing remote token"})
            continue
        body = json.loads(payload.decode("utf-8"))
        body["admin_token"] = token
        request = urllib.request.Request(
            node["url"].rstrip("/") + "/api/targets",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                response.read()
            synced.append({"id": node.get("id"), "ok": True})
        except Exception as exc:
            skipped.append({"id": node.get("id"), "reason": str(exc)[:120]})
    return synced, skipped


def ping_latency(host, timeout=2):
    started = time.perf_counter()
    proc = subprocess.run(
        ["ping", "-n", "-c", "1", "-W", str(timeout), host],
        capture_output=True,
        text=True,
        timeout=timeout + 1,
        check=False,
    )
    output = proc.stdout + proc.stderr
    match = re.search(r"time[=<]([0-9.]+)\s*ms", output)
    if proc.returncode == 0 and match:
        return float(match.group(1)), ""
    if proc.returncode == 0:
        return (time.perf_counter() - started) * 1000, ""
    return None, "icmp timeout"


def http_latency(url, timeout=4):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "vps-latency-probe/1.0"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(512)
            latency = (time.perf_counter() - started) * 1000
            if response.status >= 500:
                return latency, f"http {response.status}"
            return latency, ""
    except Exception as exc:
        return None, str(exc)[:120]


def tcp_latency(host, port, timeout=3):
    started = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return (time.perf_counter() - started) * 1000, ""
    except Exception as exc:
        return None, str(exc)[:120]


def probe_target(target):
    kind = target.get("kind", "icmp").lower()
    timeout = float(target.get("timeout_seconds", 3))
    if kind == "http":
        return http_latency(target["url"], timeout=timeout)
    if kind == "tcp":
        return tcp_latency(target["host"], target["port"], timeout=timeout)
    return ping_latency(target["host"], timeout=max(1, int(timeout)))


def local_snapshot():
    config = load_config()
    with STATE_LOCK:
        results = json.loads(json.dumps(STATE["results"]))
    return {
        "node": {
            "id": config.get("node_id", "local"),
            "name": config.get("node_name", socket.gethostname()),
            "location": config.get("location", ""),
            "status": "online",
            "updated_at": now_ms(),
            "started_at": STATE["started_at"],
        },
        "targets": sanitize_targets(config.get("targets", [])),
        "results": results,
    }


def fetch_remote_node(node):
    base = node.get("url", "").rstrip("/")
    if not base:
        raise ValueError("missing url")
    with urllib.request.urlopen(base + "/api/local", timeout=3) as response:
        data = json.loads(response.read().decode("utf-8"))
    data.setdefault("node", {})
    data["node"].setdefault("id", node.get("id") or node.get("name") or base)
    data["node"].setdefault("name", node.get("name") or data["node"]["id"])
    data["node"]["status"] = "online"
    return data


def combined_snapshot():
    config = load_config()
    snapshots = [local_snapshot()]
    for node in config.get("remote_nodes", []):
        try:
            snapshots.append(fetch_remote_node(node))
        except Exception as exc:
            snapshots.append(
                {
                    "node": {
                        "id": node.get("id") or node.get("name") or node.get("url", "remote"),
                        "name": node.get("name") or node.get("url", "Remote"),
                        "location": node.get("location", ""),
                        "status": "offline",
                        "updated_at": now_ms(),
                        "error": str(exc)[:120],
                    },
                    "targets": [],
                    "results": {},
                }
            )

    targets = {}
    for snap in snapshots:
        for target in snap.get("targets", []):
            targets[target["id"]] = target

    return {
        "generated_at": now_ms(),
        "interval_seconds": config.get("interval_seconds", 5),
        "targets": list(targets.values()),
        "nodes": snapshots,
    }


def probe_loop():
    while True:
        config = load_config()
        targets = sanitize_targets(config.get("targets", []))
        history_limit = max(10, int(config.get("history_minutes", 60)) * 60 * 1000)
        timestamp = now_ms()

        for target in targets:
            latency, error = probe_target(target)
            sample = {
                "t": timestamp,
                "latency_ms": round(latency, 2) if latency is not None else None,
                "ok": latency is not None and not error,
                "error": error,
            }
            tid = target["id"]
            with STATE_LOCK:
                bucket = STATE["results"].setdefault(tid, {"series": []})
                bucket["series"].append(sample)
                cutoff = timestamp - history_limit
                bucket["series"] = [item for item in bucket["series"] if item["t"] >= cutoff]
                bucket.update(sample)

        with STATE_LOCK:
            STATE["targets"] = targets

        time.sleep(max(2, int(config.get("interval_seconds", 5))))


class Handler(BaseHTTPRequestHandler):
    server_version = "VPSLatencyProbe/1.0"

    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 65536:
            raise ValueError("request body too large")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def is_admin(self, payload):
        config = load_config()
        expected = str(config.get("admin_token") or "")
        if not expected:
            return True
        provided = str(
            self.headers.get("X-Probe-Admin-Token")
            or payload.get("admin_token")
            or "",
        )
        return hmac.compare_digest(provided, expected)

    def send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/local":
            return self.send_json(local_snapshot())
        if parsed.path == "/api/snapshot":
            return self.send_json(combined_snapshot())
        if parsed.path == "/api/config":
            return self.send_json(public_config(load_config()))
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "time": now_ms()})
        if parsed.path in ("/", "/index.html"):
            return self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self):
        try:
            payload = self.read_json()
            if not self.is_admin(payload):
                return self.send_json({"error": "invalid admin token"}, status=401)

            parsed = urlparse(self.path)
            config = load_config()
            if parsed.path == "/api/nodes":
                node = validate_remote_node(payload.get("node") or payload)
                config["remote_nodes"] = upsert_by_id(
                    config.get("remote_nodes", []),
                    node,
                )
                save_config(config)
                public_node = dict(node)
                public_node.pop("admin_token", None)
                return self.send_json({"ok": True, "node": public_node})

            if parsed.path == "/api/targets":
                target = validate_target(payload.get("target") or payload)
                config["targets"] = upsert_by_id(config.get("targets", []), target)
                save_config(config)
                synced, skipped = [], []
                if payload.get("sync", True):
                    synced, skipped = sync_target_to_remote_nodes(config, target)
                return self.send_json(
                    {
                        "ok": True,
                        "target": target,
                        "synced": synced,
                        "skipped": skipped,
                    }
                )

            return self.send_json({"error": "not found"}, status=404)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=400)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        if parsed.path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


def main():
    config = load_config()
    threading.Thread(target=probe_loop, daemon=True).start()
    address = (config.get("bind_host", "0.0.0.0"), int(config.get("port", 8099)))
    httpd = ThreadingHTTPServer(address, Handler)
    print(f"VPS Latency Probe listening on http://{address[0]}:{address[1]}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
