import { defineConfig } from "@trigger.dev/sdk";
import { pythonExtension } from "@trigger.dev/python/extension";

export default defineConfig({
  project: process.env.TRIGGER_PROJECT_REF ?? "proj_open_tabs_local",
  maxDuration: 120,
  build: {
    extensions: [
      pythonExtension({
        devPythonBinaryPath: ".venv/bin/python",
        requirementsFile: "./requirements.txt",
        scripts: ["./backend/**/*.py"],
      }),
    ],
  },
});
