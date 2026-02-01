import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const parsed = new URL(apiUrl);

const nextConfig: NextConfig = {
  // Allow images from the API
  images: {
    remotePatterns: [
      {
        protocol: parsed.protocol.replace(":", "") as "http" | "https",
        hostname: parsed.hostname,
        port: parsed.port,
      },
    ],
  },
};

export default nextConfig;
