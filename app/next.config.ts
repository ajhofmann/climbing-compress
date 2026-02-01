import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow images from the API
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000" },
    ],
  },
};

export default nextConfig;
