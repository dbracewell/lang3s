import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const [mode, secretDirectory = join(root, "docker/secrets/local")] = process.argv.slice(2);

function database(args, input) {
  try {
    return execFileSync("docker", ["compose", "exec", "-T", "database", ...args], {
      cwd: join(root, "docker"), input, stdio: ["pipe", "pipe", "pipe"],
    });
  } catch {
    // psql errors can contain SQL with passwords; never print captured output.
    throw new Error("Database credential operation failed. Ensure the Compose database is running and ready. Existing volumes may retain an older password; use scripts/setup-env.sh <mac|linux> --force --rotate-secrets to rotate credentials.");
  }
}

try {
  if (mode === "check") {
    const env = parseEnv(readFileSync(join(root, "backend/.env"), "utf8"));
    const password = readFileSync(join(secretDirectory, "db_password.txt"), "utf8").trim();
    if ((process.env.POSTGRES_PASSWORD ?? env.POSTGRES_PASSWORD) !== password) {
      throw new Error("Backend POSTGRES_PASSWORD differs from docker/secrets/local/db_password.txt. Remove any stale shell override and regenerate .env with scripts/setup-env.sh <mac|linux> --force.");
    }
    // Use the container network: localhost inside Postgres may allow trust auth.
    database(["sh", "-ec", `
      export PGPASSWORD="$(cat /run/secrets/db_password)"
      psql -w -h database -U admin -d lang3s -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null
      export PGPASSWORD="$(cat /run/secrets/inngest_db_password)"
      psql -w -h database -U inngest -d inngest -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null
    `]);
    console.log("Database credentials verified for admin and inngest.");
  } else if (mode === "rotate") {
    const passwords = ["db_password", "inngest_db_password"].map(name => {
      const value = readFileSync(join(secretDirectory, `${name}.txt`), "utf8").trim();
      if (!/^[a-f0-9]{64}$/.test(value)) throw new Error("Rotation requires generated 64-character hexadecimal secrets.");
      return value;
    });
    // The local Unix socket permits the container administrator to recover stale
    // credentials. Both roles change in one transaction before files are replaced.
    database(["psql", "-X", "-U", "admin", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
      `BEGIN;\nALTER ROLE admin WITH PASSWORD '${passwords[0]}';\nALTER ROLE inngest WITH PASSWORD '${passwords[1]}';\nCOMMIT;\n`);
    console.log("PostgreSQL passwords rotated for admin and inngest.");
  } else {
    throw new Error("Usage: node scripts/db-secrets.mjs <check|rotate> [secret-directory]");
  }
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
