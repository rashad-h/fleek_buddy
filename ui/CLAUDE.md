# CLAUDE.md — Fleek Buddy UI

Presentation-only frontend: TanStack Start (Vite/Nitro) + Query/Form, Tailwind v4 +
shadcn/ui. All data comes from the FastAPI backend via `fetch` to `/api/*`
(proxied by the Vite dev server to `BACKEND_URL`, default `http://localhost:8000`).
No database and no LLM code live here.

## Conventions (important)

- **Imports** use the `#/*` alias (→ `src/*`) **with explicit file extensions**:
  `import { Button } from '#/components/ui/button.tsx'`.
- `verbatimModuleSyntax` is on → use `import type` for type-only imports.
  `noUnusedLocals`/`noUnusedParameters` are on → no dead imports/vars.
- Package manager is **pnpm**. Native builds are allowlisted in `pnpm-workspace.yaml`
  (`allowBuilds`) — required or Vite/esbuild break.
- `src/routeTree.gen.ts` is generated. After adding routes run `pnpm generate-routes`
  (dev/build also regenerate it).

## How to add X → see `.claude/skills/`

`routing`, `data-fetching` (Query), `forms`, `ui-components` (Tailwind/shadcn).
The `database`, `llm`, `server-functions`, `tables` skills describe template
features that were stripped from this app — ignore them.

## Layout

```
src/routes/         # pages (index dashboard, items.$itemId detail)
src/components/     # ProductCard, OfferModal, NegotiationDrawer
src/components/ui/  # shadcn/ui
src/lib/            # api.ts (fetchers + SSE), types.ts, buyer.ts, format.ts
```

## Data

- Typed fetchers in `src/lib/api.ts` wrapped with TanStack Query on the client.
- Agent replies stream over SSE; `streamAgentReply` parses `token` / `decision` /
  `error` / `done` events from a fetch ReadableStream.
- The buyer is identified by a UUID in localStorage (`src/lib/buyer.ts`).

## Gotchas

- TanStack Start is **alpha** — APIs can shift.
- SSR runs route components on the server: never touch `localStorage` or `window`
  outside effects/handlers/guards.

## Comments

Keep them sparse — only where intent isn't obvious from the code.
