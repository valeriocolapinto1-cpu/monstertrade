import { formatPercent, trendOf } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Change({ value, className }: { value: number | null; className?: string }) {
  if (value === null) return <span className={cn("num text-subtle", className)}>—</span>;
  const trend = trendOf(value);
  return (
    <span
      className={cn(
        "num",
        trend === "up" && "text-up",
        trend === "down" && "text-down",
        trend === "flat" && "text-muted-foreground",
        className,
      )}
    >
      {formatPercent(value)}
    </span>
  );
}
