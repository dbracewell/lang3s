import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { join, resolve } from "node:path";

const root = process.cwd();
const platform = process.argv[2];
const sourceIndex = process.argv.indexOf("--source");
const source = sourceIndex === -1 ? undefined : process.argv[sourceIndex + 1];

if (!["mac", "linux"].includes(platform) || !source) {
  console.error(
    "Usage: pnpm run setup:<mac|linux> --source <artifact-directory-or-url>",
  );
  process.exit(1);
}

if (platform === "mac" && process.platform !== "darwin") {
  console.error("setup:mac must run on macOS");
  process.exit(1);
}

if (platform === "linux" && process.platform !== "linux") {
  console.error("setup:linux must run on Linux");
  process.exit(1);
}

function run(command, args, cwd = root) {
  execFileSync(command, args, { cwd, stdio: "inherit" });
}

console.log("Resetting local Lang3s state: containers, volumes, secrets, env files, and filestore.");
run("docker", ["compose", "down", "--volumes", "--remove-orphans"], join(root, "docker"));

for (const path of [
  join(root, "backend/.env"),
  join(root, "frontend/.env"),
  join(root, "filestore"),
]) {
  rmSync(path, { recursive: true, force: true });
}
for (const name of [
  "db_password",
  "inngest_db_password",
  "system_api_key",
  "better_auth_secret",
  "admin_passphrase",
]) {
  rmSync(join(root, "docker/secrets", `${name}.txt`), { force: true });
}

run("bash", ["scripts/setup-env.sh", platform]);

run("pnpm", ["install"]);

run("uv", ["sync", "--all-packages"], join(root, "backend"));

// filestore:sync changes into backend, so resolve local paths from setup's cwd.
const artifactSource = /^https?:\/\//i.test(source)
  ? source
  : resolve(root, source);
run("pnpm", ["run", "filestore:sync", "--source", artifactSource]);

run(
  "docker",
  ["compose", "build", "--no-cache", "database"],
  join(root, "docker"),
);

if (platform === "mac") {
  run("docker", ["compose", "up", "-d", "--wait"], join(root, "docker"));
  run("pnpm", ["reset-db"], join(root, "backend"));
  run("pnpm", ["reset-db"], join(root, "frontend"));
} else {
  run(
    "docker",
    ["compose", "--profile", "production", "up", "--build", "-d"],
    join(root, "docker"),
  );
}

run("pnpm", ["run", "doctor"]);
