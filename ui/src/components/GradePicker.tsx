import { Input } from '#/components/ui/input.tsx'
import { Label } from '#/components/ui/label.tsx'

type GradePickerProps = {
  grades: Array<string>
  maxPieces: number
  quantities: Record<string, number>
  onChange: (quantities: Record<string, number>) => void
}

/**
 * Per-grade quantity inputs for partial offers. The exact per-grade stock is
 * seller-only, so the only cap is the bundle's total piece count; the seller
 * pushes back in chat if the ask exceeds what they hold.
 */
export function GradePicker({
  grades,
  maxPieces,
  quantities,
  onChange,
}: GradePickerProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {grades.map((grade) => (
        <div key={grade} className="flex items-center gap-2">
          <Label
            htmlFor={`grade-${grade}`}
            className="text-xs font-bold text-muted-foreground"
          >
            Grade {grade}
          </Label>
          <Input
            id={`grade-${grade}`}
            type="number"
            min={0}
            max={maxPieces}
            className="h-9 w-20"
            value={quantities[grade] ?? 0}
            onChange={(e) => {
              const quantity = Math.max(
                0,
                Math.min(maxPieces, Math.floor(Number(e.target.value) || 0)),
              )
              onChange({ ...quantities, [grade]: quantity })
            }}
          />
        </div>
      ))}
    </div>
  )
}
