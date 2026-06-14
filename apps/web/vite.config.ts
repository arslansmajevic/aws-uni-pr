import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = 'https://iekcqlmf6b.execute-api.localhost.localstack.cloud:4566'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/prod'),
      },
    },
  },
})
