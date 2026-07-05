import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Helper config to proxy API requests but bypass proxying for browser page refreshes/navigation.
// If the browser requests HTML (page load/refresh), we serve index.html to let React Router handle it.
const proxyConfig = {
  target: 'http://localhost:8000',
  bypass: (req, res, proxyOptions) => {
    if (req.headers.accept && req.headers.accept.indexOf('html') !== -1) {
      return '/index.html';
    }
  }
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/auth': proxyConfig,
      '/papers': proxyConfig,
      '/search': proxyConfig,
      '/qa': proxyConfig,
      '/analytics': proxyConfig,
      '/users': proxyConfig,
      '/health': proxyConfig,
    },
  },
})
