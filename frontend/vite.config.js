import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

function apiBypass(req) {
  // Only proxy if it's an API call (not browser navigation)
  if (req.headers.accept && req.headers.accept.includes("text/html")) {
    return "/index.html";
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    hmr: { overlay: false },
    allowedHosts: true,
    historyApiFallback: true,
    proxy: {
      "/graph": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/videos": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/search": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/segment": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/compliance": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/pipeline": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/payments": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/trackit": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/health": { target: "http://viral_backend:8000", bypass: apiBypass },
      "/categories": { target: "http://viral_backend:8000", bypass: apiBypass }
    }
  },
  define: { "process.env": {} }
})
