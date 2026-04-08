import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Vitest unit test (no vitest dep installed in this app — pure-fn
    // tests run via the python pytest suite for the same logic).
    "lib/set-narrative/scoring.test.ts",
  ]),
  {
    rules: {
      // React 19 / Next 16 introduced these as `error`. We keep them as
      // `warn` so legacy components (TanStack Table, WaveSurfer setup,
      // PlayerInteractionLevel promote/collapse, etc.) still surface
      // the issue without blocking the lint gate. New code should
      // still avoid setState-in-effect; warnings are visible in CI.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
