import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from GitHub Pages at /<repo>/ ; build output goes to repo-root /docs.
export default defineConfig({
  base: "/kredikarti-harcama-analizi/",
  plugins: [react()],
  build: {
    outDir: "../docs",
    emptyOutDir: true,
  },
  server: { port: 5173 },
});
