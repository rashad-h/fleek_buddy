import type { JobStatus } from '#/lib/merchant-types.ts'

type ProcessingStatusProps = {
  status: JobStatus | null
  message: string
  analyzedCount: number
  totalCount: number
}

const STAGE_LABELS: Record<JobStatus, string> = {
  queued: 'Queued',
  extracting: 'Extracting frames',
  describing: 'Analyzing garments with Gemini',
  summarizing: 'Building bundle listing',
  complete: 'Complete',
  error: 'Failed',
}

export function ProcessingStatus({
  status,
  message,
  analyzedCount,
  totalCount,
}: ProcessingStatusProps) {
  if (!status) return null

  const stage = STAGE_LABELS[status]
  const progress =
    status === 'complete'
      ? 100
      : status === 'summarizing'
        ? 90
        : totalCount > 0 && status === 'describing'
          ? 40 + Math.round((analyzedCount / totalCount) * 45)
          : status === 'extracting'
            ? 25
            : 10

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold">{stage}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{message}</p>
        </div>
        {totalCount > 0 && status === 'describing' && (
          <p className="text-sm font-medium text-muted-foreground">
            {analyzedCount}/{totalCount}
          </p>
        )}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
