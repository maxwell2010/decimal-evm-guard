#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${1:-/etc/decimal-guardian/config.json}"
[[ $EUID -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
[[ -f "$CONFIG_FILE" ]] || { echo "Configuration missing: $CONFIG_FILE" >&2; exit 1; }
command -v python3 >/dev/null

install -d -o root -g root -m 0700 /etc/decimal-guardian /var/lib/decimal-guardian
install -d -o root -g root -m 0755 /opt/decimal-guardian
if [[ "$(readlink -f "$CONFIG_FILE")" != "/etc/decimal-guardian/config.json" ]]; then
  install -o root -g root -m 0600 "$CONFIG_FILE" /etc/decimal-guardian/config.json
else
  chmod 0600 /etc/decimal-guardian/config.json
fi

python3 -m venv /opt/decimal-guardian/venv
/opt/decimal-guardian/venv/bin/pip install --disable-pip-version-check --quiet "$ROOT_DIR"
install -o root -g root -m 0644 "$ROOT_DIR/systemd/decimal-guardian.service" /etc/systemd/system/decimal-guardian.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/decimal-guardian.service
echo "Installed, not started. Run guard-check and doctor before starting decimal-guardian.service."
