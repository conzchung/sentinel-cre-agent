import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
  test: {
    environment: 'node',
    include: ['lib/__tests__/**/*.test.ts'],
    // Auth config is read from the environment; provide deterministic test values.
    env: {
      COOKIE_SECRET: 'test-cookie-secret',
      AUTH_USERNAME: 'demo',
      AUTH_PASSWORD: 'demo',
    },
  },
});
