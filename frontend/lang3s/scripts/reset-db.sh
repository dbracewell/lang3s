pnpm tsx --conditions=react-server --env-file=.env ./scripts/init/reset.ts
pnpm drizzle-kit push --force --config ./scripts/drizzle-empty.config.ts
pnpm drizzle-kit migrate
pnpm tsx --conditions=react-server --env-file=.env ./scripts/init/init.ts

DOCUMENTS_DIR="${DOCUMENTS_DIR:-/Users/ik/prj/Lang3s/documents}"
rm $DOCUMENTS_DIR/*.json.gz

