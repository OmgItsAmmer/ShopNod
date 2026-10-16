import path from 'node:path';
import withSerwistInit from '@serwist/next';
import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n/request.ts');
const withSerwist = withSerwistInit({
  swSrc: 'app/sw.ts',
  swDest: 'public/sw.js',
  disable: process.env.NODE_ENV === 'development',
  cacheOnNavigation: false,
});

const config: NextConfig = {
  // Small Docker image: `.next/standalone` holds only what the server needs.
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '../../'),
  transpilePackages: ['@shopnod/theme', '@shopnod/shared-types'],
  poweredByHeader: false,
  reactStrictMode: true,
};

export default withSerwist(withNextIntl(config));
