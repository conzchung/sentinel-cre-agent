/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) so the Docker
  // runtime image needs only Node + the traced deps, not the whole node_modules.
  output: 'standalone',
};
export default nextConfig;
