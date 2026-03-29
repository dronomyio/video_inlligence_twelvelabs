import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    hmr: { overlay: false },
    allowedHosts: true,
    proxy: {
      "/graph": "http://viral_backend:8000",
      "/videos": "http://viral_backend:8000",
      "/search": "http://viral_backend:8000",
      "/segment": "http://viral_backend:8000",
      "/compliance": "http://viral_backend:8000",
      "/pipeline": "http://viral_backend:8000",
      "/payments": "http://viral_backend:8000",
      "/trackit": "http://viral_backend:8000",
      "/health": "http://viral_backend:8000"
    }
  },
  define: { "process.env": {} }
})
