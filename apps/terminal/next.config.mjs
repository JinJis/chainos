/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@chainos/ui', '@chainos/graph-schema', 'three'],
  eslint: { ignoreDuringBuilds: true },
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
