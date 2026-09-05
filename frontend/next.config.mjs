import { createMDX } from "fumadocs-mdx/next";

/** @type {import("next").NextConfig} */
const nextConfig = {
  turbopack: {
    root: process.cwd(),
  },
};

const withMDX = createMDX();

export default withMDX(nextConfig);
