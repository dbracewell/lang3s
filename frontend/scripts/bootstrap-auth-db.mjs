import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

const dbPath = process.env.DATABASE_URL ?? "./users.db";
const migrationsDir = path.resolve(process.cwd(), "better-auth_migrations");

if (dbPath !== ":memory:") {
  const dir = path.dirname(dbPath);
  fs.mkdirSync(dir, { recursive: true });
}

const db = new Database(dbPath);

try {
  if (!fs.existsSync(migrationsDir)) {
    console.warn(`[auth-db] migrations dir not found: ${migrationsDir}`);
    process.exit(0);
  }

  const files = fs
    .readdirSync(migrationsDir)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  for (const file of files) {
    const sql = fs.readFileSync(path.join(migrationsDir, file), "utf8");
    const statements = sql
      .split(";")
      .map((s) => s.trim())
      .filter(Boolean);

    for (const stmt of statements) {
      try {
        db.exec(`${stmt};`);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        if (
          /already exists/i.test(message) ||
          /duplicate column name/i.test(message)
        ) {
          continue;
        }
        throw err;
      }
    }
  }

  console.log(`[auth-db] ensured schema at ${dbPath}`);
} finally {
  db.close();
}
