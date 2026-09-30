import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api/orders': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
      '/api/products': {
        target: 'http://localhost:8082',
        changeOrigin: true,
      },
      '/api/cart': {
        target: 'http://localhost:8083',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/cart/, '/api/v1/cart'),
      },
      '/api/auth': {
        target: 'http://localhost:8083',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['node_modules', 'e2e'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/',
        'src/test/',
        'src/config/',              // Static configuration
        'src/services/',            // Thin API wrappers (covered by E2E)
        'src/hooks/',               // React Query wrappers (covered by E2E)
        'src/pages/',               // Page components (covered by E2E)
        'src/types/',               // TypeScript types only
        'src/main.tsx',             // Entry point
        'src/App.tsx',              // Root component (covered by E2E)
        'src/components/layout/',   // Layout components (covered by E2E)
        'src/components/ui/Badge.tsx',   // Simple presentational
        'src/components/ui/Card.tsx',    // Simple presentational
        'src/components/ui/Input.tsx',   // Simple presentational
      ],
    },
  },
})
