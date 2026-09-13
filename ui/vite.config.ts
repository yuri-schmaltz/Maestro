import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend port resolution — the dev server proxies `/api` to the
// FastAPI backend. The default matches start_local.sh's default;
// start_local.sh also re-writes the running backend's port into
// ui/.env.local at launch time so the proxy follows the actual bind
// (launch.py falls forward to the next free port when 7860 is taken,
// so the proxy target has to be configurable, not hard-coded).
const backendPort = process.env.MAESTRO_BACKEND_PORT || process.env.VITE_BACKEND_PORT || '7860'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': `http://127.0.0.1:${backendPort}`,
    },
  },
  // Strip console.* and debugger statements from the production bundle.
  // Dev mode (npm run dev) is unaffected — esbuild `drop` only runs at
  // build time.
  esbuild: {
    drop: ['console', 'debugger'],
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
