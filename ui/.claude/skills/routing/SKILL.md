---
name: routing
description: Use when adding or changing pages, routes, dynamic/nested params, search-param validation, navigation, or route loaders in this TanStack Start template.
---

# File-Based Routing (TanStack Start)

Routes live in `src/routes/**`. Each file exports a `Route` created with `createFileRoute`. The route tree is generated into `src/routeTree.gen.ts` automatically by the Vite plugin — never edit that file, and don't import from it by hand.

## When to use

Adding a page, an API/server route, a dynamic segment, validated search params, a `loader`, or wiring navigation with `Link` / `useNavigate`.

## Conventions (this template)

- Import alias `#/*` → `src/*`, **with explicit file extensions**: `import { Button } from '#/components/ui/button.tsx'`.
- `verbatimModuleSyntax` + `noUnusedLocals` are on → use `import type` for type-only imports and don't leave unused imports.
- The root route uses `createRootRouteWithContext` and provides a `queryClient` in context (see `src/routes/__root.tsx`, `src/router.tsx`).

## Root route (`src/routes/__root.tsx`)

Defines the document shell and the router context type. This template renders the shell via `shellComponent` (not `component` + `<Outlet/>`) and declares a typed context:

```tsx
import {
  HeadContent,
  Link,
  Scripts,
  createRootRouteWithContext,
} from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'

interface MyRouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  head: () => ({
    meta: [{ charSet: 'utf-8' }, { title: 'TanStack Start Template' }],
    links: [{ rel: 'stylesheet', href: appCss }],
  }),
  shellComponent: RootDocument,
})
```

`children` is passed into `RootDocument`; the nav is defined there. Add top-level nav links inside that `<nav>`.

## Add a page route

Create `src/routes/<name>.tsx`. The path string passed to `createFileRoute` must match the file's route path.

```tsx
// src/routes/about.tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/about')({ component: About })

function About() {
  return <div className="mx-auto max-w-2xl p-8">About</div>
}
```

- Nested routes: `src/routes/posts/index.tsx` → `/posts`, `src/routes/posts/settings.tsx` → `/posts/settings`.
- Add a link to it in the `<nav>` of `__root.tsx` if it should be reachable from the header.

## Dynamic path params (`$param`)

A `$`-prefixed filename segment becomes a typed param. Read params with `Route.useParams()`.

```tsx
// src/routes/posts/$postId.tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/posts/$postId')({ component: Post })

function Post() {
  const { postId } = Route.useParams()
  return <div>Post {postId}</div>
}
```

Multiple/nested params work the same: `src/routes/users/$id/posts/$postId.tsx` yields `{ id, postId }`.

## Search-param validation

Validate and type search params with `validateSearch`. This template already depends on `zod`, so use it:

```tsx
// src/routes/search.tsx
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

const searchSchema = z.object({
  q: z.string().optional(),
  page: z.number().int().min(1).default(1),
})

export const Route = createFileRoute('/search')({
  validateSearch: searchSchema, // zod schema is a valid validator
  component: Search,
})

function Search() {
  const { q, page } = Route.useSearch() // typed + parsed
  return (
    <div>
      {q} — page {page}
    </div>
  )
}
```

## Navigation

Use `Link` for declarative navigation and `useNavigate` for imperative. Both are fully typed against the route tree — pass `params` / `search` as objects, not string-interpolated URLs.

```tsx
import { Link, useNavigate } from '@tanstack/react-router'

// Declarative
<Link to="/posts/$postId" params={{ postId: '1' }}>Post 1</Link>
<Link to="/search" search={{ page: 2 }}>Page 2</Link>

// Active styling: this template uses the tailwind [&.active] pattern (see __root.tsx)
<Link to="/items" className="[&.active]:underline">Items</Link>

// Imperative
function GoButton() {
  const navigate = useNavigate()
  return (
    <button onClick={() => navigate({ to: '/posts/$postId', params: { postId: '1' } })}>
      Go
    </button>
  )
}
```

## Route loaders

`loader` runs before the component renders (on server for SSR, then client on navigation). Read its result with `Route.useLoaderData()`. Call server functions directly from loaders.

```tsx
// src/routes/items-list.tsx
import { createFileRoute } from '@tanstack/react-router'
import { listItems } from '#/server/items.ts'

export const Route = createFileRoute('/items-list')({
  loader: () => listItems(),
  component: ItemsList,
})

function ItemsList() {
  const items = Route.useLoaderData()
  return (
    <ul>
      {items.map((i) => (
        <li key={i.id}>{i.title}</li>
      ))}
    </ul>
  )
}
```

`loader` receives `{ context, params, ... }`. The root `context` includes `queryClient`, so you can prime TanStack Query in a loader:

```tsx
loader: ({ context, params }) =>
  context.queryClient.ensureQueryData(postQueryOptions(params.postId)),
```

Note: the live `src/routes/items.tsx` page fetches via `useQuery` (client-side) rather than a loader — prefer a `loader` when you want the data ready before first paint / SSR.
