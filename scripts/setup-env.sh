#!/usr/bin/env bash
set -euo pipefail

platform="${1:-}"
force=false
rotate=false
for argument in "${@:2}"; do
  case "$argument" in
    --force) force=true ;;
    --rotate-secrets) rotate=true ;;
    *) echo "Unknown option: $argument" >&2; exit 1 ;;
  esac
done

if [[ "$platform" != "mac" && "$platform" != "linux" ]]; then
  echo "Usage: scripts/setup-env.sh <mac|linux> [--force] [--rotate-secrets]" >&2
  exit 1
fi

if [[ "$platform" == "mac" && "$(uname)" != "Darwin" ]]; then
  echo "The mac configuration can only be generated on macOS." >&2
  exit 1
fi
if [[ "$platform" == "linux" && "$(uname)" != "Linux" ]]; then
  echo "The linux configuration can only be generated on Linux." >&2
  exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_env="$root/backend/.env"
frontend_env="$root/frontend/.env"
secrets_dir="$root/docker/secrets"
mkdir -p "$secrets_dir"

if [[ ( -e "$backend_env" || -e "$frontend_env" ) && "$force" != true ]]; then
  echo "Environment files already exist. Re-run with --force to replace both." >&2
  exit 1
fi

umask 077
mkdir -p "$secrets_dir"
staged_secrets="$(mktemp -d "$secrets_dir/.staged.XXXXXX")"
trap 'rm -rf "$staged_secrets"' EXIT

generate_secret() {
  openssl rand -hex 32
}

write_secret() {
  local name="$1"
  local file="$secrets_dir/$name.txt"
  if [[ "$rotate" == true || ! -s "$file" ]]; then
    generate_secret > "$staged_secrets/$name.txt"
  else
    cp "$file" "$staged_secrets/$name.txt"
  fi
}

write_secret db_password
write_secret inngest_db_password
write_secret system_api_key
write_secret better_auth_secret
write_secret admin_passphrase

if [[ "$rotate" == true ]]; then
  # Fail before replacing any files if the existing database cannot be updated.
  node "$root/scripts/db-secrets.mjs" rotate "$staged_secrets"
fi
for name in db_password inngest_db_password system_api_key better_auth_secret admin_passphrase; do
  # Preserve the inode used by running Docker bind mounts.
  cat "$staged_secrets/$name.txt" > "$secrets_dir/$name.txt"
done

db_password="$(<"$secrets_dir/db_password.txt")"
system_key="$(<"$secrets_dir/system_api_key.txt")"
auth_secret="$(<"$secrets_dir/better_auth_secret.txt")"
admin_passphrase="$(<"$secrets_dir/admin_passphrase.txt")"
filestore_root="$root/filestore"

cat > "$backend_env" <<EOF
NODEJS_HOST=http://localhost:3000
POSTGRES_HOST=localhost
POSTGRES_USER=admin
POSTGRES_PORT=5432
POSTGRES_PASSWORD=$db_password
REDIS_HOST=localhost
REDIS_PORT=6379
SYSTEM_KEY=$system_key
FILESTORE_ROOT=$filestore_root
EOF

cat > "$frontend_env" <<EOF
INNGEST_URL=http://localhost:8288
BETTER_AUTH_SECRET=$auth_secret
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8003
ADMIN_PASSPHRASE=$admin_passphrase
SYSTEM_KEY=$system_key
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
INNGEST_SIGNING_KEY=A1B2C3
DATABASE_URL=$filestore_root/users.db
FILESTORE_ROOT=$filestore_root
EOF

echo "Created backend/.env, frontend/.env, and docker/secrets/local/."
if [[ "$rotate" == true ]]; then
  echo "Restart application services to load the rotated secrets. Existing login sessions may be invalidated."
fi
