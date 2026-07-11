---
name: database
description: Define Drizzle ORM Postgres tables, run drizzle-kit migrations, and query inside TanStack Start server functions with select/insert/update/delete.
---

# Database (Drizzle ORM + Postgres)

Use when adding or changing database tables, or reading/writing data from server functions. This template uses Drizzle ORM over `node-postgres` (`pg`).

## Layout

- `src/db/schema.ts` — table definitions and inferred types
- `src/db/index.ts` — the `db` client
- `drizzle.config.ts` — drizzle-kit config (schema path, dialect, connection)
- `drizzle/` — generated SQL migrations (created by `db:generate`)
- `src/server/*.ts` — server functions that query `db`

## The client

`src/db/index.ts` builds the client from `DATABASE_URL` and binds the schema so
queries are fully typed:

```ts
import { drizzle } from 'drizzle-orm/node-postgres'
import * as schema from './schema.ts'

export const db = drizzle(process.env.DATABASE_URL!, { schema })
```

## Defining tables

Tables live in `src/db/schema.ts`. Use `pgTable` with column builders from
`drizzle-orm/pg-core`, then export `$inferSelect` / `$inferInsert` types.

```ts
import { boolean, pgTable, serial, text, timestamp } from 'drizzle-orm/pg-core'

export const items = pgTable('items', {
  id: serial('id').primaryKey(),
  title: text('title').notNull(),
  description: text('description'), // nullable (no .notNull())
  completed: boolean('completed').notNull().default(false),
  createdAt: timestamp('created_at').notNull().defaultNow(),
})

// Row type (select) vs. insert type (defaults/serials optional)
export type Item = typeof items.$inferSelect
export type NewItem = typeof items.$inferInsert
```

Common column types: `serial`, `integer`, `text`, `boolean`, `timestamp`,
`numeric('price', { precision: 10, scale: 2 })`, `jsonb`, `text().array()`.
Chain `.notNull()`, `.default(...)` / `.defaultNow()`, `.primaryKey()`,
`.unique()`, `.references(() => other.id)`.

## Migration workflow

Config in `drizzle.config.ts` points drizzle-kit at the schema and DB. It loads
env from `.env.local` / `.env`:

```ts
import { config } from 'dotenv'
import { defineConfig } from 'drizzle-kit'

config({ path: ['.env.local', '.env'] })

export default defineConfig({
  out: './drizzle',
  schema: './src/db/schema.ts',
  dialect: 'postgresql',
  dbCredentials: { url: process.env.DATABASE_URL! },
})
```

Scripts (in `package.json`):

- `db:push` — apply the current schema straight to the DB (fast local iteration)
- `db:generate` — diff schema and write SQL migration files into `drizzle/`
- `db:migrate` — apply pending generated migrations
- `db:pull` / `db:studio` — introspect / open Drizzle Studio

In this template the DB runs in Docker, so run these through the Makefile so the
command executes inside the `app` container:

```bash
make db-push   # docker compose exec app pnpm db:push
make seed      # docker compose exec app pnpm seed
```

Use `db:push` for quick prototyping; use `db:generate` + `db:migrate` when you
want versioned migration files.

## Querying in server functions

Queries go inside `createServerFn` handlers (see `src/server/items.ts`).
Validate input with Zod in `.validator`, then run the query on `db`. Import
helpers (`eq`, `desc`, ...) from `drizzle-orm`. Note the `#/*` alias with
explicit `.ts` extensions.

```ts
import { createServerFn } from '@tanstack/react-start'
import { desc, eq } from 'drizzle-orm'
import { z } from 'zod'
import { db } from '#/db/index.ts'
import { items } from '#/db/schema.ts'

// SELECT ... ORDER BY created_at DESC
export const listItems = createServerFn().handler(async () => {
  return db.select().from(items).orderBy(desc(items.createdAt))
})

// INSERT ... RETURNING — .returning() gives back the inserted row(s)
export const createItem = createServerFn({ method: 'POST' })
  .validator((data: unknown) =>
    z
      .object({ title: z.string().min(1), description: z.string().optional() })
      .parse(data),
  )
  .handler(async ({ data }) => {
    const [row] = await db.insert(items).values(data).returning()
    return row
  })

// UPDATE ... WHERE ... RETURNING
export const toggleItem = createServerFn({ method: 'POST' })
  .validator((data: unknown) =>
    z.object({ id: z.number(), completed: z.boolean() }).parse(data),
  )
  .handler(async ({ data }) => {
    const [row] = await db
      .update(items)
      .set({ completed: data.completed })
      .where(eq(items.id, data.id))
      .returning()
    return row
  })

// DELETE ... WHERE
export const deleteItem = createServerFn({ method: 'POST' })
  .validator((data: unknown) => z.object({ id: z.number() }).parse(data))
  .handler(async ({ data }) => {
    await db.delete(items).where(eq(items.id, data.id))
    return { id: data.id }
  })
```

Tips:

- `select()` returns an array; destructure `const [row] = ...` when you expect one.
- Filter with `eq`, `ne`, `gt`, `lt`, `and`, `or`, `inArray` (from `drizzle-orm`).
- `.returning()` works on `insert`/`update`/`delete`; pass columns to narrow it.
- `db.query.<table>.findMany(...)` is available since the schema is bound in `drizzle(..., { schema })`.
