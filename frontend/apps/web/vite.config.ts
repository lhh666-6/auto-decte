import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

import { runtimePolicyForPath } from "./src/pwa/cache-policy";
import { PWA_CACHE_ID } from "./src/pwa/pwa-cache-names";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["icons/icon-192x192.png", "icons/icon-512x512.png"],
      manifest: false, // we provide our own manifest.webmanifest in public/
      workbox: {
        cacheId: PWA_CACHE_ID,
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => runtimePolicyForPath(url.pathname) === "NetworkOnly",
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    allowedHosts: [".loca.lt", "localhost"],
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
