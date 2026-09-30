import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    rollupOptions: {
      output: {
        // Separate long-lived vendor chunks so a redeploy of app code doesn't bust their cache.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/](recharts|d3-[^\\/]+|victory-vendor)[\\/]/.test(id)) return "charts";
          if (/[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return "react";
          return "vendor";
        },
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
  },
});
