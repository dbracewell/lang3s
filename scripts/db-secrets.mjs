import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const [mode, secretDirectory = join(root, "docker/secrets")] = process.argv.slice(2);

function database(args, input) {
  try {
    return execFileSync("docker", ["compose", "exec", "-T", "database", ...args], {
      cwd: join(root, "docker"),
      input,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch {
    throw new Error(
      "Database credential operation failed. Ensure the Compose database is running and ready.",
    );
  }
}

function password(name) {
  const value = readFileSync(join(secretDirectory, `${name}.txt`), "utf8").trim();
  if (!/^[a-f0-9]{64}$/.test(value)) {
    throw new Error("Database secrets must be 64-character hexadecimal values.");
  }
  return value;
}

try {
  if (mode === "check") {
    const env = parseEnv(readFileSync(join(root, "backend/.env"), "utf8"));
    if ((process.env.POSTGRES_PASSWORD ?? env.POSTGRES_PASSWORD) !== password("db_password")) {
      throw new Error(
        "Backend POSTGRES_PASSWORD differs from docker/secrets/db_password.txt.",
      );
    }
    for (const [role, db, secret] of [
      ["admin", "lang3s", "db_password"],
      ["inngest", "inngest", "inngest_db_password"],
    ]) {
      database([
        "sh",
        "-ec",
        `export PGPASSWORD="$(cat /run/secrets/${secret})"; psql -X -w -h database -U ${role} -d ${db} -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null`,
      ]);
    }
    console.log("Database credentials verified for admin and inngest.");
  } else if (mode === "rotate") {
    const adminPassword = password("db_password");
    const inngestPassword = password("inngest_db_password");
    database(
      ["psql", "-X", "-U", "admin", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
      `BEGIN;\nALTER ROLE admin WITH PASSWORD '${adminPassword}';\nALTER ROLE inngest WITH PASSWORD '${inngestPassword}';\nCOMMIT;\n`,
    );
    console.log("PostgreSQL passwords rotated for admin and inngest.");
  } else {
    throw new Error("Usage: node scripts/db-secrets.mjs <check|rotate> [secret-directory]");
  }
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
