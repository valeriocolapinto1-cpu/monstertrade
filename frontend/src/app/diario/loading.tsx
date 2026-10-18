import { Skeleton } from "@/components/skeleton";

export default function Loading() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Caricamento">
      <Skeleton className="h-6 w-24" />
      <Skeleton className="h-20 w-full rounded-md" />
      <div className="space-y-px rounded-md border bg-card">
        {[0, 1, 2].map((i) => (
          <div key={i} className="grid gap-4 px-4 py-4 lg:grid-cols-2">
            <div className="space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
            <Skeleton className="h-24 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
