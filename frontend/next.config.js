/**
 * Next.js configuration file (JavaScript version).
 * This replaces the previous TypeScript config which is no longer supported.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
