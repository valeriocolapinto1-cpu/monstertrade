import { Skeleton } from "@/components/skeleton";

export default function Loading() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Caricamento strumenti">
      <Skeleton className="h-6 w-32" />
      {[4, 6, 3].map((rows, g) => (
        <div key={g} className="rounded-md border bg-card">
          <div className="border-b px-4 py-2">
            <Skeleton className="h-3 w-20" />
          </div>
          {Array.from({ length: rows }, (_, i) => (
            <div key={i} className="flex items-center justify-between border-b px-4 py-3 last:border-0">
              <div className="space-y-1.5">
                <Skeleton className="h-3.5 w-36" />
                <Skeleton className="h-2.5 w-16" />
              </div>
              <Skeleton className="h-3.5 w-24" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
