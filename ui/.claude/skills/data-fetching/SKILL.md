---
name: data-fetching
description: Fetch and mutate server data with TanStack Query (useQuery, useMutation, invalidateQueries) over this template's TanStack Start server functions.
---

# Data Fetching with TanStack Query

Use this when a route needs to read or write server state. This template pairs TanStack Query with TanStack Start server functions from `src/server/items.ts` — server functions do the actual data access, TanStack Query handles caching, loading/error state, and refetching.

## What's already wired

The `QueryClient` and SSR integration are set up for you — do NOT add a `QueryClientProvider` or create your own `QueryClient` in routes.

- `src/integrations/tanstack-query/root-provider.tsx` builds the client and exposes it as router context:

  ```tsx
  import { QueryClient } from '@tanstack/react-query'

  export function getContext() {
    const queryClient = new QueryClient()
    return { queryClient }
  }
  ```

- `src/router.tsx` puts that context on the router and enables SSR dehydration/hydration via `setupRouterSsrQueryIntegration`, so queries prefetched/run during SSR are hydrated on the client automatically:

  ```tsx
  const context = getContext()
  const router = createTanStackRouter({ routeTree, context /* ... */ })
  setupRouterSsrQueryIntegration({ router, queryClient: context.queryClient })
  ```

Inside components, get the client with `useQueryClient()` — never construct a new one.

## Reading data with useQuery

Call the server function in `queryFn`. Server functions are invoked as `fn()` (no args) or `fn({ data })`.

```tsx
import { useQuery } from '@tanstack/react-query'
import { listItems } from '#/server/items.ts'

const {
  data: items = [],
  isPending,
  isError,
} = useQuery({
  queryKey: ['items'],
  queryFn: () => listItems(),
})
```

- `queryKey` uniquely identifies and caches the query; it's also what you invalidate against.
- Default a possibly-`undefined` `data` (e.g. `data: items = []`) so first render is safe.

## Writing data with useMutation

`mutationFn` calls a `POST` server function. On success, invalidate the affected query so the UI refetches fresh data.

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createItem, toggleItem, deleteItem } from '#/server/items.ts'

const queryClient = useQueryClient()
const invalidate = () => queryClient.invalidateQueries({ queryKey: ['items'] })

const create = useMutation({
  // server fn signature: createItem({ data: { title, description? } })
  mutationFn: (value: { title: string; description?: string }) =>
    createItem({ data: value }),
  onSuccess: invalidate,
})

const toggle = useMutation({
  mutationFn: (value: { id: number; completed: boolean }) =>
    toggleItem({ data: value }),
  onSuccess: invalidate,
})

const remove = useMutation({
  mutationFn: (id: number) => deleteItem({ data: { id } }),
  onSuccess: invalidate,
})
```

Trigger a mutation with `mutate(vars)` (fire-and-forget) or `await mutateAsync(vars)` (when you need the result or to sequence work, e.g. resetting a form after create). Use `create.isPending` to disable buttons while in flight.

## Cache invalidation

`queryClient.invalidateQueries({ queryKey: ['items'] })` marks matching queries stale and refetches active ones. Return the promise from `onSuccess` if you want the mutation to stay pending until the refetch completes:

```tsx
onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] })
```

Query-key matching is prefix-based: invalidating `['items']` also matches `['items', id]`. Pass `exact: true` to match only the exact key.

## Notes for this template

- Import server functions from `#/server/items.ts` with the explicit `.ts` extension (alias `#/*` → `src/*`).
- Use `import type` for type-only imports (e.g. `import type { Item } from '#/db/schema.ts'`) — `verbatimModuleSyntax` is on.
- See `src/routes/items.tsx` for the full working example combining `useQuery`, three mutations, and shared invalidation.
