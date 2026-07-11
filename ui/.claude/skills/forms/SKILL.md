---
name: forms
description: Build type-safe forms with TanStack Form (useForm, form.Field render prop, handleSubmit, reset, Zod field validation) matching this template.
---

# Forms with TanStack Form

Use this when a route needs user input. TanStack Form is headless and fully typed from `defaultValues` — pair it with the template's `Input`/`Button` UI components and submit through a TanStack Query mutation (see the `data-fetching` skill and `src/routes/items.tsx`).

## Create the form with useForm

`defaultValues` defines the form's shape and types. `onSubmit` receives the validated `value`.

```tsx
import { useForm } from '@tanstack/react-form'

const form = useForm({
  defaultValues: { title: '', description: '' },
  onSubmit: async ({ value }) => {
    await create.mutateAsync(value) // create = a useMutation
    form.reset() // clear back to defaultValues
  },
})
```

- `form.reset()` restores `defaultValues`; pass `form.reset(values)` to reset to new values.
- Because `onSubmit` is `async`, you can `await` a mutation and only `reset()` after it succeeds.

## Wire up submission

Prevent the native submit and delegate to `form.handleSubmit()` (returns a promise — `void` it in the handler):

```tsx
<form
  onSubmit={(e) => {
    e.preventDefault()
    void form.handleSubmit()
  }}
>
  {/* fields + submit button */}
  <Button type="submit" disabled={create.isPending}>
    Add
  </Button>
</form>
```

## Fields with the render-prop

Each input is a `form.Field` whose child is a function receiving `field`. Bind `field.state.value` to the input and call `field.handleChange` on change. `name` is type-checked against `defaultValues`.

```tsx
import { Input } from '#/components/ui/input.tsx'

;<form.Field name="title">
  {(field) => (
    <Input
      placeholder="Title"
      value={field.state.value}
      onChange={(e) => field.handleChange(e.target.value)}
    />
  )}
</form.Field>
```

For blur-based validation, also wire `onBlur={field.handleBlur}`.

## Field-level validation

Pass a `validators` object on the field. A validator can be a function returning an error string (or `undefined` when valid), or a Zod schema.

Function validator:

```tsx
<form.Field
  name="title"
  validators={{
    onChange: ({ value }) =>
      value.trim().length === 0 ? 'Title is required' : undefined,
  }}
>
  {(field) => (
    <>
      <Input
        value={field.state.value}
        onBlur={field.handleBlur}
        onChange={(e) => field.handleChange(e.target.value)}
      />
      {!field.state.meta.isValid && (
        <em role="alert">{field.state.meta.errors.join(', ')}</em>
      )}
    </>
  )}
</form.Field>
```

Zod schema validator (a schema can be passed directly — TanStack Form runs it and surfaces its messages):

```tsx
import { z } from 'zod'

;<form.Field
  name="title"
  validators={{ onChange: z.string().min(1, 'Title is required') }}
>
  {(field) => (
    <>
      <Input
        value={field.state.value}
        onChange={(e) => field.handleChange(e.target.value)}
      />
      {field.state.meta.isTouched && !field.state.meta.isValid && (
        <em role="alert">
          {field.state.meta.errors.map((e) => e?.message).join(', ')}
        </em>
      )}
    </>
  )}
</form.Field>
```

Read validation state from `field.state.meta`: `isValid`, `isTouched`, `errors`, `isValidating`. With function validators `errors` holds strings; with Zod schemas the entries are issue objects (use `e?.message`).

## Notes for this template

- Import UI components with explicit extensions (`#/components/ui/input.tsx`, `#/components/ui/button.tsx`).
- `verbatimModuleSyntax` is on — use `import type` for type-only imports; `noUnusedLocals` means don't leave unused destructured values.
- The end-to-end example (form + Zod-validated server function + mutation) lives in `src/routes/items.tsx` and `src/server/items.ts`.
