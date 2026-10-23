/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",          // minimal self-contained server for the Docker image
  poweredByHeader: false,
};

module.exports = nextConfig;
