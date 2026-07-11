import { useRef, useState } from 'react'

import { Button } from '#/components/ui/button.tsx'

type VideoUploadProps = {
  disabled?: boolean
  defaultCount?: number
  onUpload: (file: File, expectedCount: number) => void
  onSample: (expectedCount: number) => void
}

export function VideoUpload({
  disabled = false,
  defaultCount = 12,
  onUpload,
  onSample,
}: VideoUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [expectedCount, setExpectedCount] = useState(defaultCount)

  return (
    <div className="rounded-lg border border-dashed bg-card p-8 text-center">
      <p className="text-lg font-bold">Upload supplier video</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Extract garments, analyze each with Gemini, then summarize into one
        marketplace listing.
      </p>
      <label className="mt-6 inline-flex items-center gap-2 text-sm">
        <span className="font-medium text-muted-foreground">Expected items</span>
        <input
          type="number"
          min={1}
          max={40}
          value={expectedCount}
          disabled={disabled}
          onChange={(event) =>
            setExpectedCount(
              Math.max(1, Math.min(40, Number(event.target.value) || 1)),
            )
          }
          className="h-9 w-20 rounded-md border border-input bg-background px-2 text-center text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
      </label>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          Choose video
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          onClick={() => onSample(expectedCount)}
        >
          Use demo sample
        </Button>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onUpload(file, expectedCount)
          event.target.value = ''
        }}
      />
    </div>
  )
}
