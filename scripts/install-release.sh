#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
command -v curl >/dev/null
command -v sha256sum >/dev/null
command -v python3 >/dev/null

REPO="https://github.com/maxwell2010/decimal-guardian"
TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  TAG="$(curl -fsSL --retry 3 https://api.github.com/repos/maxwell2010/decimal-guardian/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
fi
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid release tag" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT
ARCHIVE="decimal-guardian-${TAG}.tar.gz"
BASE="${REPO}/releases/download/${TAG}"
curl -fsSL --retry 3 "${BASE}/${ARCHIVE}" -o "${WORK}/${ARCHIVE}"
curl -fsSL --retry 3 "${BASE}/${ARCHIVE}.sha256" -o "${WORK}/${ARCHIVE}.sha256"
(cd "$WORK" && sha256sum -c "${ARCHIVE}.sha256")
mkdir -p "$WORK/source"
tar -xzf "${WORK}/${ARCHIVE}" -C "$WORK/source" --strip-components=1
install -d -o root -g root -m 0700 /etc/decimal-guardian
if [[ ! -e /etc/decimal-guardian/config.json ]]; then
  install -o root -g root -m 0600 "$WORK/source/config.example.json" /etc/decimal-guardian/config.json
  echo "Created disabled example config. Review it before enabling services."
fi
bash "$WORK/source/scripts/install.sh" /etc/decimal-guardian/config.json
