import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/healthz",
        destination: "http://api:8000/healthz",
      },
    ];
  },
};

export default nextConfig;