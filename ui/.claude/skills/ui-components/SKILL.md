---
name: ui-components
description: Add and build shadcn/ui components (new-york style) with Tailwind v4, the cn helper, and cva variants in this template.
---

# UI components (shadcn/ui + Tailwind v4)

Use when adding a UI primitive (button, input, dialog, ...) or building a custom component
with variants. This template uses **Tailwind CSS v4** (via `@tailwindcss/vite`, configured
in CSS) and **shadcn/ui** style `new-york`, with components in `src/components/ui/`.

## Add a component with the CLI

The CLI copies the component source into `src/components/ui/` so you own and can edit it.

```bash
pnpm dlx shadcn@latest add button
pnpm dlx shadcn@latest add dialog input label   # several at once
```

Config lives in `components.json`. Key points for this template:

- `style: "new-york"`, `iconLibrary: "lucide"`, `baseColor: "zinc"`, `cssVariables: true`.
- Aliases resolve through the **`#/` import alias** (→ `src/`), so generated imports look
  like `#/components/ui/...` and `#/lib/utils`.
- The Tailwind entry CSS is `src/styles.css` (there is no `tailwind.config.*`).

Because of `verbatimModuleSyntax` + `noUnusedLocals`, after generating a component:

- Import values and types separately: `import type { VariantProps } from '...'`.
- In this repo, local imports use **explicit extensions** (e.g. `#/lib/utils.ts`).
  Generated shadcn imports (`#/lib/utils`) resolve fine, but match the surrounding files'
  style when editing by hand.

## The `cn` helper (`src/lib/utils.ts`)

`cn` merges class lists and resolves Tailwind conflicts (last wins). Use it wherever you
combine base classes with a `className` prop or conditional classes.

```ts
import type { ClassValue } from 'clsx'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

```tsx
import { cn } from '#/lib/utils.ts'

;<div className={cn('px-2', isActive && 'bg-accent', className)} />
```

## Variants with class-variance-authority (see button.tsx)

shadcn components define style variants with `cva`, then expose them as typed props via
`VariantProps`. This is the pattern to copy for your own variant-driven components.

```tsx
import * as React from 'react'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'

import { cn } from '#/lib/utils.ts'

const buttonVariants = cva(
  // base classes applied to every variant
  'inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-white hover:bg-destructive/90',
        outline:
          'border bg-background hover:bg-accent hover:text-accent-foreground',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3',
        lg: 'h-10 rounded-md px-6',
        icon: 'size-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

function Button({
  className,
  variant = 'default',
  size = 'default',
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  // asChild renders children as the element (via Slot) instead of a <button>.
  const Comp = asChild ? Slot.Root : 'button'
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
```

Usage — variants become typed props, and `className` still merges via `cn`:

```tsx
<Button variant="destructive" size="sm">Delete</Button>
<Button variant="outline" className="w-full">Save</Button>
```

## Theme tokens (Tailwind v4, in `src/styles.css`)

There is no JS config. Tailwind is imported and themed directly in CSS:

- `@import 'tailwindcss';` pulls in Tailwind (the `@tailwindcss/vite` plugin wires the
  build; no `content` globs needed).
- Design tokens (colors, fonts, radii) are CSS variables under `:root` and `.dark`
  (colors are `oklch(...)`), then mapped to Tailwind utilities inside `@theme inline`.

```css
@import 'tailwindcss';

:root {
  --primary: oklch(0.21 0.006 285.885);
  --primary-foreground: oklch(0.985 0 0);
  --radius: 0.625rem;
}
.dark {
  --primary: oklch(0.985 0 0);
  --primary-foreground: oklch(0.21 0.006 285.885);
}

/* Map CSS variables to Tailwind tokens → enables bg-primary, text-primary-foreground, rounded-md, etc. */
@theme inline {
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --radius-md: calc(var(--radius) - 2px);
}
```

To add a semantic color: declare `--my-token` in both `:root` and `.dark`, then add
`--color-my-token: var(--my-token);` inside `@theme inline` to get `bg-my-token`,
`text-my-token`, etc. Dark mode is driven by the `dark` class
(`@custom-variant dark (&:is(.dark *))`), so `dark:` utilities and the `.dark` token
overrides work together.
