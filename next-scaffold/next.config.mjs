/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // Recommended for Docker deployments
  images: {
    unoptimized: true, // For exporting static pages easily without vercel logic blocking
  },
  experimental: {
    optimizePackageImports: ["recharts", "lucide-react"], // Reduces bundle sizes instantly
  },
};

export default nextConfig;
