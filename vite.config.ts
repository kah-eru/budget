import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./assets", import.meta.url)) } },
  build: {
    outDir: "budget/static/budget/dist",
    emptyOutDir: true,
    lib: {
      entry: "assets/app.tsx",
      formats: ["es"],
      fileName: () => "app.js",
      cssFileName: "app",
    },
  },
});
