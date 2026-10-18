export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "down" | "warn";
}) {
  const tones = {
    neutral: "border-border-strong text-muted-foreground",
    down: "border-down/40 text-down",
    warn: "border-warn/40 text-warn",
  };
  return (
    <span className={`num rounded-sm border px-1 py-px text-2xs leading-none ${tones[tone]}`}>
      {children}
    </span>
  );
}
