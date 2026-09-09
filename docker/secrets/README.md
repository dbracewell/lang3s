The files in this directory are examples. Real credentials belong in the ignored
`local/` directory and must not be committed.

Generate configuration from the repository root:

```sh
bash scripts/setup-env.sh mac
```

Use `linux` on Linux. Existing secrets are reused. `--force` regenerates both
`.env` files from those secrets without rotating passwords.

Setup waits for PostgreSQL and checks the backend password against the secret,
then authenticates both `admin` and `inngest` over the Docker network. A mismatch
stops setup before database initialization or production application startup.
PostgreSQL only applies its initial password when creating a new data volume.

To rotate secrets for an existing installation, keep the Compose database running:

```sh
bash scripts/setup-env.sh mac --force --rotate-secrets
node scripts/db-secrets.mjs check
```

Rotation stages new secrets, updates both database roles in one transaction using
the container's local administrator connection, then writes the secret files and
`.env` files. If the database update fails, the existing files remain unchanged.
No database data is deleted. Rotation requires an initialized database with both
roles; for a fresh installation, omit `--rotate-secrets`.

Restart running application services after rotation so they load the new secrets.
For Docker services, run `docker compose restart` from `docker/`. Authentication
secret rotation may invalidate existing login sessions. Keep the generated secrets
with the database volume when moving or restoring an installation.
