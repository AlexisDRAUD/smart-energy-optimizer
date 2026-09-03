import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import pluginReact from "eslint-plugin-react";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist", "node_modules"]),
  { files: ["**/*.{js,mjs,cjs,ts,mts,cts,jsx,tsx}"], plugins: { js }, extends: ["js/recommended"], languageOptions: { globals: globals.browser } },
  tseslint.configs.recommended,
  pluginReact.configs.flat.recommended,
  pluginReact.configs.flat["jsx-runtime"],
  { settings: { react: { version: "detect" } } },
  {
    files: ["tests/**/*.{ts,tsx}", "src/**/*.{test,spec}.{ts,tsx}"],
    languageOptions: { globals: { ...globals.jest, ...globals.node } },
  },
  {
    files: ["**/*.{cjs,cts}", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
]);
