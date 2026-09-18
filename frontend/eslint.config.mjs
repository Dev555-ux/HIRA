import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

// Motion import guard (T2.1). Two rules, both about keeping the bundle honest:
//
//   framer-motion is the package's legacy name. It still resolves, so an
//   import would work and quietly reintroduce a second copy of the library.
//
//   motion-plus is the paid tier. It cannot be installed without a member's
//   access token, so this fails early and for the right reason rather than at
//   npm install time.
const forbiddenPackages = [
  {
    name: "framer-motion",
    message: "Import from 'motion/react' (or 'motion/react-m' for elements) — framer-motion is the legacy package name.",
  },
  {
    name: "motion-plus",
    message: "Motion+ is a paid tier and is out of scope for this project. Use the free APIs in 'motion/react'.",
  },
];

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [".next/**", "out/**", "build/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    rules: {
      "no-restricted-imports": [
        "error",
        { paths: forbiddenPackages, patterns: ["motion-plus/*"] },
      ],
    },
  },
  {
    // The marketing tree renders inside LazyMotion, where the full `motion`
    // component defeats the code-splitting the provider exists for — and with
    // `strict` it throws at runtime. `m` is the element to use there.
    files: ["src/components/marketing/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            ...forbiddenPackages,
            {
              name: "motion/react",
              importNames: ["motion"],
              message:
                "Use `import * as m from 'motion/react-m'` inside the marketing tree — the full `motion` component breaks LazyMotion's code splitting.",
            },
          ],
          patterns: ["motion-plus/*"],
        },
      ],
    },
  },
];

export default eslintConfig;
