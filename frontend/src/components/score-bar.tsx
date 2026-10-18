import { cn } from "@/lib/utils";

/** Barra centrata da −100 a +100 (o da −1 a +1 con `unit`). */
export function ScoreBar({
  value,
  max = 100,
  className,
  label,
}: {
  value: number | null;
  max?: number;
  className?: string;
  label: string;
}) {
  const min = -max;
  const v = value === null ? 0 : Math.max(min, Math.min(max, value));
  const width = (Math.abs(v) / max) * 50;
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value ?? 0}
      className={cn("relative h-1.5 w-full rounded-full bg-surface-hover", className)}
    >
      <span aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
      {value !== null && (
        <span
          aria-hidden
          className={cn("absolute inset-y-0 rounded-full", v >= 0 ? "bg-up" : "bg-down")}
          style={v >= 0 ? { left: "50%", width: `${width}%` } : { right: "50%", width: `${width}%` }}
        />
      )}
    </div>
  );
}
