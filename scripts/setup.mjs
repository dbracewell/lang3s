import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

const root = process.cwd();
const platform = process.argv[2];
const sourceIndex = process.argv.indexOf("--source");
const source = sourceIndex === -1 ? undefined : process.argv[sourceIndex + 1];

if (!['mac', 'linux'].includes(platform) || !source) {
  console.error("Usage: pnpm run setup:<mac|linux> --source <artifact-directory-or-url>");
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

const backendEnv = existsSync(join(root, "backend/.env"));
const frontendEnv = existsSync(join(root, "frontend/.env"));
if (!backendEnv && !frontendEnv) {
  run("bash", ["scripts/setup-env.sh", platform]);
} else if (backendEnv !== frontendEnv) {
  console.error("backend/.env and frontend/.env must either both exist or both be absent.");
  process.exit(1);
}
run("pnpm", ["install"]);
run("uv", ["sync", "--all-packages"], join(root, "backend"));
// filestore:sync changes into backend, so resolve local paths from setup's cwd.
const artifactSource = /^https?:\/\//i.test(source) ? source : resolve(root, source);
run("pnpm", ["run", "filestore:sync", "--source", artifactSource]);

if (platform === "mac") {
  run("docker", ["compose", "up", "-d"], join(root, "docker"));
  run("pnpm", ["bootstrap-db"], join(root, "backend"));
} else {
  run("docker", ["compose", "--profile", "production", "up", "--build", "-d"], join(root, "docker"));
}

run("pnpm", ["run", "doctor"]);
