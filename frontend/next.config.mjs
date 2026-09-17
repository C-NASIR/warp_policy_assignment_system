import { createMDX } from "fumadocs-mdx/next";
import { readFileSync } from "node:fs";

const learnRedirects = JSON.parse(
  readFileSync(new URL("./lib/learn-redirects.json", import.meta.url), "utf8"),
);

/** @type {import("next").NextConfig} */
const nextConfig = {
  output: "standalone",
  redirects() {
    return Object.entries(learnRedirects).map(([source, destination]) => ({
      source,
      destination,
      permanent: true,
    }));
  },
  turbopack: {
    root: process.cwd(),
  },
};

const withMDX = createMDX();

export default withMDX(nextConfig);
