/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Workspace packages ship raw TS; let Next transpile them.
  transpilePackages: ['@chainos/ui', '@chainos/graph-schema'],
  // Lint is run separately in CI; don't block builds on it.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
