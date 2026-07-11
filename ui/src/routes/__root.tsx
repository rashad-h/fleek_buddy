import {
  HeadContent,
  Link,
  Scripts,
  createRootRouteWithContext,
} from '@tanstack/react-router'

import appCss from '../styles.css?url'

import type { QueryClient } from '@tanstack/react-query'

interface MyRouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  head: () => ({
    meta: [
      {
        charSet: 'utf-8',
      },
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1',
      },
      {
        title: 'Fleek Buddy — Wholesale Bundles',
      },
    ],
    links: [
      {
        rel: 'stylesheet',
        href: appCss,
      },
    ],
  }),
  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <header className="sticky top-0 z-40 border-b bg-background">
          <nav className="mx-auto flex h-14 max-w-6xl items-center px-6">
            <Link
              to="/"
              className="text-lg font-extrabold tracking-tight text-foreground"
            >
              FLEEK BUDDY
              <span className="text-accent">.</span>
            </Link>
          </nav>
        </header>
        {children}
        <Scripts />
      </body>
    </html>
  )
}
