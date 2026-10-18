import { cn } from "@/lib/utils";

export function KpiStrip({ children }: { children: React.ReactNode }) {
  return (
    <dl className="grid grid-cols-2 overflow-hidden rounded-md border bg-card sm:grid-cols-4 [&>div]:border-b [&>div]:border-r sm:[&>div]:border-b-0 [&>div:nth-child(2n)]:border-r-0 sm:[&>div:nth-child(2n)]:border-r sm:[&>div:last-child]:border-r-0">
      {children}
    </dl>
  );
}

export function Kpi({
  label,
  value,
  sub,
  tone,
  meter,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "up" | "down" | "warn";
  meter?: { value: number; max: number; warn?: boolean };
}) {
  return (
    <div className="px-4 py-3">
      <dt className="text-2xs uppercase tracking-wider text-subtle">{label}</dt>
      <dd
        className={cn(
          "num mt-1 text-lg font-medium",
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          tone === "warn" && "text-warn",
        )}
      >
        {value}
      </dd>
      {meter && (
        <div
          role="meter"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={meter.max}
          aria-valuenow={meter.value}
          className="mt-2 h-1 overflow-hidden rounded-full bg-surface-hover"
        >
          <div
            className={cn("h-full rounded-full", meter.warn ? "bg-warn" : "bg-primary")}
            style={{ width: `${Math.min(100, (meter.value / Math.max(meter.max, 1e-9)) * 100)}%` }}
          />
        </div>
      )}
      {sub && <p className="num mt-1 text-2xs text-subtle">{sub}</p>}
    </div>
  );
}
