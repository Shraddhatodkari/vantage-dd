import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  build: {
    rollupOptions: {
      output: {
        // function form: react-router 7 imports react-dom internally, so object-form chunks pulled react-dom into "charts"
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (/node_modules[\\/](react|react-dom|scheduler|react-router|cookie|set-cookie-parser)[\\/]/.test(id)) return "react";
          if (/node_modules[\\/](recharts|d3-[^\\/]+|victory-vendor|lodash|recharts-scale|decimal\.js-light|eventemitter3|react-smooth|clsx|tiny-invariant|internmap|fast-equals|react-is|prop-types)[\\/]/.test(id)) return "charts";
          if (/node_modules[\\/](react-markdown|remark-|rehype-|mdast-|micromark|unified|hast-|unist-|vfile|property-information|space-separated|comma-separated|html-url|devlop|bail|trough|is-plain-obj|decode-named|character-|ccount|markdown-table|longest-streak|zwitch|estree-util|style-to|inline-style|trim-lines|extend)/.test(id)) return "markdown";
          return undefined;
        },
      },
    },
  },
});
