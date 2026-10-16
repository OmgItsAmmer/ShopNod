import { defineConfig } from 'vitest/config';

// Own config so vitest doesn't pick up the shop-web app config from the parent folder.
export default defineConfig({ test: { environment: 'node' } });
