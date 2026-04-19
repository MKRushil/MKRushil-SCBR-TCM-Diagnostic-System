import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path' // 1. 改回 'path' (拿掉 node: 前綴)
import { fileURLToPath, URL } from 'url' // 2. 改回 'url' (拿掉 node: 前綴)

// 3. 模擬 __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // Ensure it listens on all interfaces
    proxy: {
      '/api': {
        // 在 Docker 網路中，後端服務名稱為 'backend'
        target: process.env.VITE_API_TARGET || 'http://backend:8000',
        changeOrigin: true,
        rewrite: (pathStr) => pathStr.replace(/^\/api/, '/api/v1')
      }
    }
  }
})