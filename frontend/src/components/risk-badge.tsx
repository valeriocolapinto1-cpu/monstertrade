import type { RiskLabel } from "@/lib/api";
import { cn } from "@/lib/utils";

const STYLE: Record<RiskLabel, string> = {
  Basso: "border-border-strong text-muted-foreground",
  Medio: "border-border-strong text-foreground",
  Alto: "border-warn/50 text-warn",
  "Molto alto": "border-warn bg-warn-muted text-warn",
};

export function RiskBadge({ label, className }: { label: RiskLabel; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 text-2xs font-medium leading-none",
        STYLE[label],
        className,
      )}
    >
      <span className="sr-only">Rischio </span>
      {label}
    </span>
  );
}
