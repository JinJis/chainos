import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle for Docker (`node apps/terminal/server.js`).
  output: 'standalone',
  transpilePackages: ['@chainos/ui', '@chainos/graph-schema', 'three'],
  eslint: { ignoreDuringBuilds: true },
  experimental: {
    // Trace workspace packages from the monorepo root into the standalone output.
    outputFileTracingRoot: join(__dirname, '../../'),
  },
  webpack: (config) => {
    // Workspace packages use ESM ".js" import specifiers but ship ".ts" source.
    config.resolve.extensionAlias = {
      '.js': ['.ts', '.tsx', '.js'],
      '.mjs': ['.mts', '.mjs'],
    };
    return config;
  },
};

export default nextConfig;
