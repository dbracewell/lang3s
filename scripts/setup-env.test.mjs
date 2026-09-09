import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir, platform } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const target = platform() === "darwin" ? "mac" : "linux";

test("setup reuses secrets and rotates database credentials before replacing files", () => {
  const root = mkdtempSync(join(tmpdir(), "lang3s-secrets-test-"));
  try {
    for (const dir of ["scripts", "backend", "frontend", "docker", "bin"]) mkdirSync(join(root, dir));
    for (const file of ["setup-env.sh", "db-secrets.mjs"]) copyFileSync(new URL(file, import.meta.url), join(root, "scripts", file));
    writeFileSync(join(root, "bin/docker"), `#!/bin/sh
cat > "$TEST_ROOT/sql"
cp "$TEST_ROOT/docker/secrets/db_password.txt" "$TEST_ROOT/password-at-call"
exit "$DOCKER_EXIT"
`, { mode: 0o700 });
    const env = { ...process.env, PATH: `${join(root, "bin")}:${process.env.PATH}`, TEST_ROOT: root, DOCKER_EXIT: "0" };
    delete env.POSTGRES_PASSWORD;
    const setup = (...args) => execFileSync("bash", [join(root, "scripts/setup-env.sh"), target, ...args], { env, stdio: "pipe" });
    const secret = () => readFileSync(join(root, "docker/secrets/db_password.txt"), "utf8");
    setup();
    const original = secret();
    const originalEnv = readFileSync(join(root, "backend/.env"), "utf8");
    assert.match(original, /^[a-f0-9]{64}\n$/);
    assert.ok(originalEnv.includes(`POSTGRES_PASSWORD=${original.trim()}`));
    setup("--force");
    assert.equal(secret(), original);
    assert.throws(() => setup());

    env.DOCKER_EXIT = "1";
    assert.throws(() => setup("--force", "--rotate-secrets"));
    assert.equal(secret(), original);
    assert.equal(readFileSync(join(root, "backend/.env"), "utf8"), originalEnv);

    env.DOCKER_EXIT = "0";
    setup("--force", "--rotate-secrets");
    assert.notEqual(secret(), original);
    assert.equal(readFileSync(join(root, "password-at-call"), "utf8"), original);
    const sql = readFileSync(join(root, "sql"), "utf8");
    assert.ok(sql.startsWith("BEGIN;\n"));
    assert.ok(sql.includes(`ALTER ROLE admin WITH PASSWORD '${secret().trim()}';`));
    assert.ok(sql.includes("ALTER ROLE inngest WITH PASSWORD"));
    assert.ok(sql.endsWith("COMMIT;\n"));
    assert.ok(readFileSync(join(root, "backend/.env"), "utf8").includes(`POSTGRES_PASSWORD=${secret().trim()}`));

    const check = () => execFileSync(process.execPath, [join(root, "scripts/db-secrets.mjs"), "check"], { env, stdio: "pipe" });
    check();
    env.POSTGRES_PASSWORD = "stale-override";
    assert.throws(check, /Backend POSTGRES_PASSWORD differs/);
    delete env.POSTGRES_PASSWORD;
    env.DOCKER_EXIT = "1";
    assert.throws(check, /Database credential operation failed/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
