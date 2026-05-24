#!/usr/bin/env bash
set -euo pipefail

APP_NAME="vps-latency-probe"
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
PORT="${PORT:-8099}"
NODE_NAME="${NODE_NAME:-$(hostname)}"
LOCATION="${LOCATION:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash install.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install it first." >&2
  exit 1
fi

if ! command -v ping >/dev/null 2>&1; then
  echo "ping is required. Install iputils-ping first." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "${INSTALL_DIR}/static"
install -m 0755 "${SCRIPT_DIR}/app.py" "${INSTALL_DIR}/app.py"
install -m 0644 "${SCRIPT_DIR}/static/index.html" "${INSTALL_DIR}/static/index.html"

if [ ! -f "${INSTALL_DIR}/config.json" ]; then
  install -m 0600 "${SCRIPT_DIR}/config.example.json" "${INSTALL_DIR}/config.json"
  ADMIN_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
  python3 - "$INSTALL_DIR/config.json" "$PORT" "$NODE_NAME" "$LOCATION" "$ADMIN_TOKEN" <<'PY'
import json
import re
import socket
import sys

path, port, node_name, location, token = sys.argv[1:6]
with open(path, "r", encoding="utf-8") as f:
    config = json.load(f)

node_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", node_name.lower()).strip("-")
if not node_id:
    node_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", socket.gethostname().lower()).strip("-")

config["node_id"] = node_id or "vps-node"
config["node_name"] = node_name
config["location"] = location
config["port"] = int(port)
config["admin_token"] = token

with open(path, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
else
  ADMIN_TOKEN="$(python3 - "$INSTALL_DIR/config.json" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    print(json.load(f).get("admin_token", ""))
PY
)"
fi

cat >"${SERVICE_FILE}" <<EOF
[Unit]
Description=VPS Latency Probe Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/app.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${APP_NAME}.service"

echo
echo "VPS Latency Probe installed."
echo "URL: http://$(hostname -I | awk '{print $1}'):${PORT}/"
echo "Install dir: ${INSTALL_DIR}"
echo "Service: ${APP_NAME}.service"
echo "Admin token: ${ADMIN_TOKEN}"
echo
echo "Use this token in the web UI when adding VPS nodes or targets."
