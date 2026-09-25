import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [tailwindcss()],
  // Relative base so lazily loaded chunks resolve next to app.js under Django's static URL.
  base: "./",
  resolve: { alias: { "@": fileURLToPath(new URL("./assets", import.meta.url)) } },
  build: {
    outDir: "budget/static/budget/dist",
    emptyOutDir: true,
    modulePreload: false,
    rolldownOptions: {
      input: "assets/app.tsx",
      output: { entryFileNames: "app.js", chunkFileNames: "[name]-[hash].js", assetFileNames: "[name][extname]" },
      onwarn: (w, warn) => w.code === "MODULE_LEVEL_DIRECTIVE" || warn(w),
    },
  },
});
