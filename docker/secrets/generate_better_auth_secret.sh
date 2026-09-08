#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
OUT_FILE="${SCRIPT_DIR}/better_auth_secret.txt"

if [ "${1:-}" = "--force" ]; then
  FORCE=1
else
  FORCE=0
fi

if [ -f "$OUT_FILE" ] && [ "$FORCE" -ne 1 ]; then
  echo "Refusing to overwrite existing secret: $OUT_FILE"
  echo "Use --force to regenerate it."
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required but was not found on PATH" >&2
  exit 1
fi

# 64 random bytes, base64-encoded (~88 chars). Strip newlines for env-safe value.
SECRET="$(openssl rand -base64 64 | tr -d '\r\n')"
printf '%s' "$SECRET" > "$OUT_FILE"

echo "Wrote BETTER_AUTH_SECRET to: $OUT_FILE"
