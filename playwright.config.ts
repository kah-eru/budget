import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8000", channel: "chrome" },
  reporter: "list",
  outputDir: ".local/browser-results",
});
