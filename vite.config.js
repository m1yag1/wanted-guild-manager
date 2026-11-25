import { execSync } from "node:child_process";
import { defineConfig } from "vite";

// The git tag is the version (ADR 0008). Between tags, `git describe` gives
// e.g. "v0.1.0-3-g1a2b3c4", and "-dirty" when there are uncommitted changes.
function gitVersion() {
  try {
    return execSync("git describe --tags --always --dirty", {
      encoding: "utf8",
    }).trim();
  } catch {
    return "dev";
  }
}

const version = process.env.APP_VERSION ?? gitVersion();

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    {
      // dist/version.json lets every environment report what it is running.
      name: "version-file",
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "version.json",
          source: JSON.stringify(
            { version, builtAt: new Date().toISOString() },
            null,
            2,
          ),
        });
      },
    },
  ],
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.js"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.js"],
      reporter: ["text", "html"],
      thresholds: { 100: true },
    },
  },
});
