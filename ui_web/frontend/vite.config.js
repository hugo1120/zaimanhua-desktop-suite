/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
var backendPort = process.env.VITE_BACKEND_PORT || "8001";
var backendHttp = "http://127.0.0.1:".concat(backendPort);
var backendWs = "ws://127.0.0.1:".concat(backendPort);
export default defineConfig({
    plugins: [react()],
    define: {
        __ZAIMANHUA_BACKEND_ORIGIN__: JSON.stringify(process.env.VITE_BACKEND_ORIGIN || ""),
    },
    server: {
        port: 5173,
        strictPort: false,
        proxy: {
            "/api": {
                target: backendHttp,
                changeOrigin: true,
            },
            "/ws": {
                target: backendWs,
                ws: true,
            },
        },
    },
    test: {
        environment: "jsdom",
        setupFiles: "./src/test/setup.ts",
    },
});
