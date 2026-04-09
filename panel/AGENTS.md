<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Gotchas

- **`bun` / `bunx` may be missing from PATH** (macOS Claude sessions). Fallback: `./node_modules/.bin/eslint <file>` and `./node_modules/.bin/tsc --noEmit` from `panel/`. These are always installed as local deps.
- **`react-hooks/set-state-in-effect` fires on localStorage hydration** (`useState(default) → useEffect(setState(fromStorage))`). This is the canonical pattern — suppress with `// eslint-disable-next-line react-hooks/set-state-in-effect` on the setter line only.
