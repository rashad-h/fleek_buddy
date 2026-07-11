import { Link, createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { fetchItems } from '#/lib/api.ts'
import { ProductCard } from '#/components/ProductCard.tsx'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const { data: items = [], isLoading } = useQuery({
    queryKey: ['items'],
    queryFn: fetchItems,
  })

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="text-2xl font-extrabold tracking-tight">Most Wanted</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Wholesale bundles from verified vendors. All prices include shipping.
      </p>
      {isLoading ? (
        <p className="mt-12 text-center text-muted-foreground">
          Loading bundles…
        </p>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {items.map((item) => (
            <Link
              key={item.id}
              to="/items/$itemId"
              params={{ itemId: String(item.id) }}
            >
              <ProductCard item={item} />
            </Link>
          ))}
        </div>
      )}
    </main>
  )
}
