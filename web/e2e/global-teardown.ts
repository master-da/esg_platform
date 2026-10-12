import { execFileSync } from "node:child_process";
import path from "node:path";

// Remove the projects this suite created in the demo company, so the dev database stays clean.
export default function globalTeardown() {
  execFileSync("uv", ["run", "python", "-m", "scripts.clean_e2e"], {
    cwd: path.resolve(__dirname, "../../engine"),
    stdio: "inherit",
  });
}
