import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Les variables VITE_ sont lues dans le .env de la racine du depot,
  // pas dans services/web. Vite n expose que celles prefixees VITE_.
  envDir: '../../',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
})
