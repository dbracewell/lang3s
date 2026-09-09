import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

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

for (const envFile of ["backend/.env", "frontend/.env"]) {
  if (!existsSync(join(root, envFile))) {
    console.error(`${envFile} is missing; copy and configure its .env.example first.`);
    process.exit(1);
  }
}

function run(command, args, cwd = root) {
  execFileSync(command, args, { cwd, stdio: "inherit" });
}

run("pnpm", ["install"]);
run("uv", ["sync", "--all-packages"], join(root, "backend"));
run("pnpm", ["run", "filestore:sync", "--source", source]);

if (platform === "mac") {
  run("docker", ["compose", "up", "-d"], join(root, "docker"));
  run("pnpm", ["bootstrap-db"], join(root, "backend"));
} else {
  run("docker", ["compose", "--profile", "production", "up", "--build", "-d"], join(root, "docker"));
}

run("pnpm", ["run", "doctor"]);
