/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // Recommended for Docker deployments
  images: {
    unoptimized: true, // For exporting static pages easily without vercel logic blocking
  },
  experimental: {
    // `recharts` was removed from this list because Next 14's barrel-import
    // optimizer can't resolve recharts@3.x's deep dependency on `reselect`
    // (it splits recharts into per-export chunks that lose visibility into
    // their own transitive deps). Lucide is fine — it has no peer-dep chain.
    optimizePackageImports: ["lucide-react"],
  },
  // Three.js + react-three-fiber occasionally ship ESM-only modules that
  // Next's webpack config needs to transpile explicitly.
  // `recharts` is here because Next 14 auto-applies barrel optimisation to
  // popular packages, and recharts@3.x's chunked exports break when their
  // transitive `reselect` import is split out. Transpiling forces a normal
  // module-resolution path.
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei", "recharts"],
};

export default nextConfig;
