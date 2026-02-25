pnpm tsx --conditions=react-server --env-file=.env ./scripts/init/reset.ts
pnpm drizzle-kit push --force --config ./scripts/drizzle-empty.config.ts
pnpm drizzle-kit migrate
pnpm tsx --conditions=react-server --env-file=.env ./scripts/init/init.ts

FILESTORE_DIR="${FILESTORE_DIR:-/Users/ik/prj/Lang3s/filestore}"
find $FILESTORE_DIR/documents/ -maxdepth 1 -type f -delete
find $FILESTORE_DIR/annotations/ -maxdepth 1 -type f -delete
rm $FILESTORE_DIR/analytics.duckdb*

MODELS_DIR="$FILESTORE_DIR/models"
rm $MODELS_DIR/online_reducer.pkl

