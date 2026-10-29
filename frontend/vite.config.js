import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { strictPort: true, proxy: { '/api': { target: process.env.CITYMIND_BACKEND_URL || 'http://127.0.0.1:8000', rewrite: path => path.replace(/^\/api/, '') } } },
  preview: { proxy: { '/api': { target: process.env.CITYMIND_BACKEND_URL || 'http://127.0.0.1:8000', rewrite: path => path.replace(/^\/api/, '') } } },
});
