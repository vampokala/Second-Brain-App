import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const devApiTarget =
  typeof process.env.VITE_DEV_API_PROXY_TARGET === 'string' && process.env.VITE_DEV_API_PROXY_TARGET.trim() !== ''
    ? process.env.VITE_DEV_API_PROXY_TARGET.trim().replace(/\/$/, '')
    : 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Same-origin `/…` fetch in dev; override target if API runs elsewhere (e.g. Docker on another port).
      '/health': { target: devApiTarget, changeOrigin: true },
      '/config': { target: devApiTarget, changeOrigin: true },
      '/metrics': { target: devApiTarget, changeOrigin: true },
      '/sessions': { target: devApiTarget, changeOrigin: true },
      '/query': { target: devApiTarget, changeOrigin: true },
      '/ingest': { target: devApiTarget, changeOrigin: true },
      '/events': { target: devApiTarget, changeOrigin: true },
      '/admin': { target: devApiTarget, changeOrigin: true },
      '/reindex': { target: devApiTarget, changeOrigin: true },
      '/vault': { target: devApiTarget, changeOrigin: true },
      '/chats': { target: devApiTarget, changeOrigin: true },
      '/settings': { target: devApiTarget, changeOrigin: true },
      '/connectors': { target: devApiTarget, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'cobertura'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/api/generated.ts',
      ],
      thresholds: {
        lines: 80,
        branches: 70,
        functions: 80,
        statements: 80,
      },
    },
  },
})
