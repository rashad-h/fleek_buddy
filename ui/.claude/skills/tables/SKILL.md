---
name: tables
description: Build data tables with TanStack Table (createColumnHelper, useReactTable, flexRender) and add sorting, filtering, or pagination.
---

# TanStack Table (data tables)

Use when rendering tabular data with headless, type-safe columns. This template uses
`@tanstack/react-table` v8. The reference implementation is `src/routes/items.tsx`.

## When to use

- You have an array of typed rows and want columns, cell renderers, and (optionally)
  interactive sorting / filtering / pagination.
- It is headless: TanStack Table computes rows/headers; you render the markup and apply
  the template's Tailwind + shadcn styles.

## Core setup (matches items.tsx)

Steps: define a typed column helper, build a `columns` array, create the table with a row
model, then render header groups and rows via `flexRender`.

```tsx
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { Button } from '#/components/ui/button.tsx' // note: explicit .tsx extension
import type { Item } from '#/db/schema.ts'

// Typed once against the row shape; drives accessor keys and cell info types.
const columnHelper = createColumnHelper<Item>()

const columns = [
  // accessor column: pulls a value by key; `info.getValue()` is typed.
  columnHelper.accessor('title', { header: 'Title' }),

  // accessor with a custom cell renderer.
  columnHelper.accessor('description', {
    header: 'Description',
    cell: (info) => info.getValue() ?? '—',
  }),

  // accessor with access to the whole row via info.row.original.
  columnHelper.accessor('completed', {
    header: 'Done',
    cell: (info) => (
      <input type="checkbox" checked={info.getValue()} readOnly />
    ),
  }),

  // display column: no underlying value, needs an explicit `id`. Use for actions.
  columnHelper.display({
    id: 'actions',
    cell: (info) => (
      <Button variant="destructive" size="sm">
        Delete {info.row.original.id}
      </Button>
    ),
  }),
]

function ItemsTable({ data }: { data: Array<Item> }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <table className="w-full border-collapse text-left">
      <thead>
        {table.getHeaderGroups().map((headerGroup) => (
          <tr key={headerGroup.id} className="border-b">
            {headerGroup.headers.map((header) => (
              <th key={header.id} className="py-2 pr-4 font-medium">
                {/* flexRender handles string, JSX, or function headers/cells */}
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext(),
                )}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr key={row.id} className="border-b">
            {row.getVisibleCells().map((cell) => (
              <td key={cell.id} className="py-2 pr-4">
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

Notes:

- Column types: `accessor(key | fn, ...)` for data columns, `display({ id, ... })` for
  action/selection columns (no value), `group({ header, columns })` to nest headers.
- An accessor **function** (`columnHelper.accessor((row) => ..., { id, ... })`) requires an
  explicit `id`.
- `flexRender` is what lets `header`/`cell` be a plain string, JSX, or a render function.

## Add sorting / filtering / pagination

Each feature is opt-in: import its row model, pass it to `useReactTable`, and hold the
matching state. Row models compose — pass every one you need.

```tsx
import { useState } from 'react'
import {
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from '@tanstack/react-table'
import type { ColumnFiltersState, SortingState } from '@tanstack/react-table'

const [sorting, setSorting] = useState<SortingState>([])
const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])

const table = useReactTable({
  data,
  columns,
  state: { sorting, columnFilters },
  onSortingChange: setSorting,
  onColumnFiltersChange: setColumnFilters,
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  initialState: { pagination: { pageIndex: 0, pageSize: 10 } },
})
```

Wire the UI to table methods:

```tsx
// Sorting: click a header to toggle asc → desc → none.
<th
  onClick={header.column.getToggleSortingHandler()}
  className={header.column.getCanSort() ? 'cursor-pointer select-none' : ''}
>
  {flexRender(header.column.columnDef.header, header.getContext())}
  {{ asc: ' ↑', desc: ' ↓' }[header.column.getIsSorted() as string] ?? ''}
</th>

// Column filter input (per-column).
<Input
  value={(header.column.getFilterValue() as string) ?? ''}
  onChange={(e) => header.column.setFilterValue(e.target.value)}
/>

// Pagination controls.
<Button
  variant="outline"
  size="sm"
  onClick={() => table.previousPage()}
  disabled={!table.getCanPreviousPage()}
>
  Prev
</Button>
<span>
  Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
</span>
<Button
  variant="outline"
  size="sm"
  onClick={() => table.nextPage()}
  disabled={!table.getCanNextPage()}
>
  Next
</Button>
```

Tips:

- `getRowModel()` already reflects sorting, filtering, and the current page — keep
  rendering it as in the core setup; nothing in the `<tbody>` changes.
- For a search box over all columns, use `getFilteredRowModel()` plus
  `state.globalFilter` / `onGlobalFilterChange` and `table.setGlobalFilter(value)`.
- Disable sorting on a column with `enableSorting: false` in its column def.
- Memoize `columns` (and `data`) with `useMemo` when they are defined inside the component
  to avoid needless re-renders.
