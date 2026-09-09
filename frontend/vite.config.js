import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
    globals: false,
  },
  server: {
    // Bind IPv4 explicitly. Listening only on [::1] makes
    // http://127.0.0.1:5173 fail, which is what most Windows browsers
    // and the Cursor preview use when the user opens localhost.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/readiness": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
