pnpm drizzle-kit push --force --config ./scripts/drizzle-empty.config.ts 
pnpm drizzle-kit push

pnpm tsx --conditions=react-server --env-file=.env ./scripts/init_db.ts
pnpm tsx --conditions=react-server --env-file=.env ./scripts/clear_redis.ts

DOCUMENTS_DIR="${DOCUMENTS_DIR:-/Users/ik/prj/Lang3s/documents}"
rm $DOCUMENTS_DIR/*.json.gz


