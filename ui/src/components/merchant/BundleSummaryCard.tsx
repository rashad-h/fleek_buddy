import type { BundleSummary } from '#/lib/merchant-types.ts'

export function BundleSummaryCard({ summary }: { summary: BundleSummary }) {
  return (
    <section className="rounded-lg border bg-card p-5 shadow-sm">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        Bundle listing
      </p>
      <h2 className="mt-1 text-xl font-extrabold tracking-tight">
        {summary.short_title}
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">{summary.description}</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{summary.piece_count} pcs</span>
        <span>{summary.condition_overall}</span>
        {summary.brands.length > 0 && <span>{summary.brands.join(' · ')}</span>}
        {summary.materials.length > 0 && (
          <span>{summary.materials.join(' · ')}</span>
        )}
      </div>
      {summary.highlights.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {summary.highlights.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {summary.needs_review && (
        <p className="mt-3 text-xs font-semibold text-sale">Needs review</p>
      )}
    </section>
  )
}
