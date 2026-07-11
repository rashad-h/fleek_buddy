import { Link, createFileRoute } from '@tanstack/react-router'
import { useCallback, useEffect, useState } from 'react'

import { BundleSummaryCard } from '#/components/merchant/BundleSummaryCard.tsx'
import { GarmentCard } from '#/components/merchant/GarmentCard.tsx'
import { ProcessingStatus } from '#/components/merchant/ProcessingStatus.tsx'
import { VideoUpload } from '#/components/merchant/VideoUpload.tsx'
import { Button } from '#/components/ui/button.tsx'
import {
  createMerchantJob,
  createSampleMerchantJob,
  publishMerchantJob,
  streamMerchantJob,
} from '#/lib/merchant-api.ts'
import type {
  BundleSummary,
  GarmentAttributes,
  JobStatus,
  MerchantItem,
} from '#/lib/merchant-types.ts'

export const Route = createFileRoute('/merchant')({
  component: MerchantDashboard,
})

function mergeItem(
  items: Array<MerchantItem>,
  index: number,
  patch: Partial<MerchantItem>,
): Array<MerchantItem> {
  return items.map((item) =>
    item.index === index ? { ...item, ...patch } : item,
  )
}

function MerchantDashboard() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [message, setMessage] = useState('')
  const [items, setItems] = useState<Array<MerchantItem>>([])
  const [summary, setSummary] = useState<BundleSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishedCount, setPublishedCount] = useState<number | null>(null)

  const analyzedCount = items.filter((item) => item.status === 'complete').length
  const canPublish =
    status === 'complete' && summary != null && publishedCount === null

  const startStream = useCallback((id: string) => {
    void streamMerchantJob(id, {
      onStatus: (event) => {
        setStatus(event.status)
        setMessage(event.message)
      },
      onFramesReady: (event) => {
        setItems(event.items)
      },
      onItemAnalyzed: (event) => {
        setItems((current) =>
          mergeItem(current, event.index, {
            status: event.error ? 'error' : 'complete',
            attributes: event.attributes as GarmentAttributes | null,
            error: event.error,
          }),
        )
      },
      onSummaryReady: (event) => {
        setSummary(event.summary)
      },
      onError: (detail) => {
        setError(detail)
        setStatus('error')
      },
      onDone: () => {
        setBusy(false)
        setStatus((current) => current ?? 'complete')
      },
    })
  }, [])

  const beginJob = useCallback(
    async (starter: () => Promise<{ job_id: string }>) => {
      setBusy(true)
      setError(null)
      setItems([])
      setSummary(null)
      setStatus('queued')
      setMessage('Starting…')
      setPublishedCount(null)
      try {
        const { job_id } = await starter()
        setJobId(job_id)
        startStream(job_id)
      } catch (err) {
        setBusy(false)
        setError(err instanceof Error ? err.message : 'Could not start job')
        setStatus('error')
      }
    },
    [startStream],
  )

  useEffect(() => {
    if (status === 'complete' && message === '') {
      setMessage(
        summary
          ? `Ready: ${summary.short_title}`
          : `Cataloged ${items.length} items`,
      )
    }
  }, [status, message, items.length, summary])

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">
            Merchant catalog
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            One video becomes one marketplace listing, built from every garment
            Gemini sees.
          </p>
        </div>
        <Link
          to="/"
          className="text-sm font-semibold text-foreground underline-offset-4 hover:underline"
        >
          Browse marketplace
        </Link>
      </div>

      <div className="mt-6 space-y-6">
        {!jobId && (
          <VideoUpload
            disabled={busy}
            onUpload={(file, count) =>
              void beginJob(() => createMerchantJob(file, count))
            }
            onSample={(count) =>
              void beginJob(() => createSampleMerchantJob(count))
            }
          />
        )}

        {(status || error) && (
          <ProcessingStatus
            status={status}
            message={error ?? message}
            analyzedCount={analyzedCount}
            totalCount={items.length}
          />
        )}

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {summary && <BundleSummaryCard summary={summary} />}

        {items.length > 0 && (
          <section>
            <h2 className="text-lg font-bold">
              Garments in this video
              <span className="ml-2 text-sm font-medium text-muted-foreground">
                {items.length}
              </span>
            </h2>
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              {items.map((item) => (
                <GarmentCard key={item.filename} item={item} />
              ))}
            </div>
          </section>
        )}

        {jobId && status === 'complete' && (
          <div className="flex flex-wrap items-center gap-3">
            {canPublish && (
              <Button
                type="button"
                disabled={publishing}
                onClick={() => {
                  void (async () => {
                    setPublishing(true)
                    setError(null)
                    try {
                      const result = await publishMerchantJob(jobId)
                      setPublishedCount(result.count)
                    } catch (err) {
                      setError(
                        err instanceof Error ? err.message : 'Publish failed',
                      )
                    } finally {
                      setPublishing(false)
                    }
                  })()
                }}
              >
                {publishing ? 'Publishing…' : 'Publish bundle to marketplace'}
              </Button>
            )}
            {publishedCount != null && (
              <p className="text-sm text-muted-foreground">
                Published 1 bundle listing.{' '}
                <Link
                  to="/"
                  className="font-semibold underline-offset-4 hover:underline"
                >
                  View marketplace
                </Link>
              </p>
            )}
            <button
              type="button"
              className="text-sm font-semibold text-muted-foreground underline-offset-4 hover:underline"
              onClick={() => {
                setJobId(null)
                setStatus(null)
                setMessage('')
                setItems([])
                setSummary(null)
                setError(null)
                setPublishedCount(null)
              }}
            >
              Process another video
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
