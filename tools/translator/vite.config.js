import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const root = path.resolve(import.meta.dirname);

export default defineConfig({
  plugins: [react()],
  root,
  server: {
    fs: { allow: [path.resolve(root, "../..")] },
  },
  resolve: {
    alias: {
      papaparse: path.resolve(root, "node_modules/papaparse"),
      react: path.resolve(root, "node_modules/react"),
      "react-dom": path.resolve(root, "node_modules/react-dom"),
    },
  },
});