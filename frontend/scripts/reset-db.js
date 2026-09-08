const fs = require("node:fs");
const { execSync } = require("node:child_process");

const dbPath = process.env.DATABASE_URL;

if (!dbPath) {
  console.error("❌ Error: DATABASE_URL is not defined in .env");
  process.exit(1);
}

// Delete the main DB and any SQLite temporary files (-wal, -shm)
const filesToDelete = [dbPath, `${dbPath}-wal`, `${dbPath}-shm`];

console.log("🗑️ Deleting old database files...");
filesToDelete.forEach((file) => {
  if (fs.existsSync(file)) {
    fs.rmSync(file, { force: true });
    console.log(`Deleted: ${file}`);
  }
});

console.log("✨ Running migrations...");
// Run the migration command and pass the output directly to the terminal
execSync(
  "pnpm dlx --allow-build=better-sqlite3 auth@latest migrate --config src/lib/auth/auth.ts --yes",
  { stdio: "inherit" },
);
