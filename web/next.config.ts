import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every page here is per-user and must show fresh numbers immediately after an edit
  // (uploads, categorization, calculations). Request-time rendering keeps that simple and
  // avoids serving cached figures, so Cache Components / partial prefetching stay off.
  cacheComponents: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
