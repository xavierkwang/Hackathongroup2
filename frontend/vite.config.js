import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In local mode the API runs on :8787 (python backend/local_server.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow GitHub Codespaces' forwarded URLs (*.app.github.dev)
    allowedHosts: ['.app.github.dev', 'localhost', '127.0.0.1'],
    proxy: { '/api': 'http://127.0.0.1:8787' },
  },
})
