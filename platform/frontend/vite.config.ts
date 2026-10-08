import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    watch: {
      // Poll for file changes so edits on the host are detected inside the
      // Docker container on macOS (native fs events do not cross the bind mount).
      usePolling: true,
      interval: 300
    }
  }
});
