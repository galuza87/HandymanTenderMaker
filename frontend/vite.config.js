import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Custom middleware shield to prevent Vite from crashing on malformed URIs
const uriShieldPlugin = () => ({
  name: 'uri-shield',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      try {
        if (req.url) {
          decodeURI(req.url);
          decodeURIComponent(req.url);
        }
      } catch (err) {
        if (err instanceof URIError) {
          res.statusCode = 400;
          res.end('Bad Request: Malformed URI');
          return;
        }
      }
      next();
    });
  }
});

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), uriShieldPlugin()],
  server: {
    host: '0.0.0.0',
    port: 5173, // or your preferred port
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
})
