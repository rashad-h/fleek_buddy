import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-4xl font-bold">Fleek Buddy</h1>
    </div>
  )
}
