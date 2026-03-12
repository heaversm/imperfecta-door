import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["@imgly/background-removal-node", "sharp"],
};

export default nextConfig;
