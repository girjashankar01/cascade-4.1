import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/sources': 'http://127.0.0.1:8000',
      '/analyze': 'http://127.0.0.1:8000',
      '/claims': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/manifest': 'http://127.0.0.1:8000',
      '/commit': 'http://127.0.0.1:8000',
      '/approve': 'http://127.0.0.1:8000',
      '/versions': 'http://127.0.0.1:8000',
      '/verify-version': 'http://127.0.0.1:8000',
      '/verify': 'http://127.0.0.1:8000',
      '/execute': 'http://127.0.0.1:8000',
      '/verifications': 'http://127.0.0.1:8000',
      '/deployments': 'http://127.0.0.1:8000',
      '/balances': 'http://127.0.0.1:8000',
      '/proposals': 'http://127.0.0.1:8000',
      '/scenarios': 'http://127.0.0.1:8000',
    },
  },
})
