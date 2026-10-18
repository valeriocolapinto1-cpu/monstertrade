import { Skeleton } from "@/components/skeleton";

export default function Loading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Caricamento strumento">
      <Skeleton className="h-3 w-20" />
      <div className="flex items-end justify-between">
        <div className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-7 w-48" />
        </div>
        <Skeleton className="h-8 w-36" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <Skeleton className="h-[420px] w-full rounded-md sm:h-[510px]" />
        <Skeleton className="h-64 w-full rounded-md" />
      </div>
    </div>
  );
}
