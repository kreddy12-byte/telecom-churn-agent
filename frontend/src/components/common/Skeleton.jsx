export default function Skeleton({ className = "h-4 w-full" }) {
  return (
    <div
      className={`skeleton-shimmer rounded-control bg-surface-interactive/80 ${className}`}
      aria-hidden="true"
    />
  );
}

export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="surface overflow-hidden" aria-busy="true" aria-label="Loading table">
      <div className="divide-y divide-line">
        {Array.from({ length: rows }).map((_, row) => (
          <div key={row} className="grid gap-4 px-4 py-3 md:grid-cols-5">
            {Array.from({ length: cols }).map((__, col) => (
              <Skeleton key={col} className="h-3 w-full" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function KpiSkeleton({ count = 4 }) {
  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      aria-busy="true"
      aria-label="Loading metrics"
    >
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="surface px-4 py-3.5">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-3 h-7 w-16" />
          <Skeleton className="mt-3 h-3 w-28" />
        </div>
      ))}
    </div>
  );
}

export function ChartSkeleton({ className = "h-52" }) {
  const heights = [40, 65, 45, 80, 55, 70, 50];
  return (
    <div
      className={`chart-shell flex items-end gap-2 ${className}`}
      aria-busy="true"
      aria-label="Loading chart"
    >
      {heights.map((height, index) => (
        <div
          key={index}
          className="skeleton-shimmer flex-1 rounded-control bg-surface-interactive/80"
          style={{ height: `${height}%` }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 ri-enter" aria-busy="true" aria-label="Loading page">
      <div>
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-3 h-7 w-64 max-w-full" />
        <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      </div>
      <KpiSkeleton />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>
      <TableSkeleton rows={5} />
    </div>
  );
}

export function OverviewSkeleton() {
  return (
    <div className="space-y-5 ri-enter" aria-busy="true" aria-label="Loading overview">
      <div>
        <Skeleton className="h-3 w-28" />
        <Skeleton className="mt-3 h-7 w-72 max-w-full" />
        <Skeleton className="mt-3 h-4 w-[28rem] max-w-full" />
      </div>
      <KpiSkeleton count={3} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartSkeleton />
        <div className="surface space-y-3 px-4 py-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      </div>
      <ChartSkeleton className="h-56" />
      <TableSkeleton rows={5} />
    </div>
  );
}

export function CustomersSkeleton() {
  return (
    <div className="space-y-5 ri-enter" aria-busy="true" aria-label="Loading customers">
      <div>
        <Skeleton className="h-7 w-56 max-w-full" />
        <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      </div>
      <div className="surface flex flex-wrap gap-3 px-4 py-3.5">
        <Skeleton className="h-10 w-full max-w-sm" />
        <Skeleton className="h-10 w-44" />
        <Skeleton className="h-10 w-24" />
      </div>
      <TableSkeleton rows={8} />
    </div>
  );
}

export function CustomerIntelligenceSkeleton() {
  return (
    <div className="space-y-5 ri-enter" aria-busy="true" aria-label="Loading customer intelligence">
      <div>
        <Skeleton className="h-3 w-40" />
        <Skeleton className="mt-3 h-7 w-48" />
        <Skeleton className="mt-3 h-4 w-72 max-w-full" />
      </div>
      <div className="surface grid gap-6 px-5 py-5 lg:grid-cols-[14rem_1fr]">
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-28" />
          <Skeleton className="h-6 w-20" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartSkeleton />
        <div className="surface space-y-3 px-4 py-4">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </div>
    </div>
  );
}

export function ActionsSkeleton() {
  return (
    <div className="space-y-5 ri-enter" aria-busy="true" aria-label="Loading retention actions">
      <div>
        <Skeleton className="h-7 w-52 max-w-full" />
        <Skeleton className="mt-3 h-4 w-80 max-w-full" />
      </div>
      <KpiSkeleton count={4} />
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-8 w-20" />
        ))}
      </div>
      <TableSkeleton rows={6} />
    </div>
  );
}

export function BatchAnalysisSkeleton() {
  return (
    <div className="space-y-5 ri-enter" aria-busy="true" aria-label="Loading batch analysis">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="surface space-y-4 px-4 py-4">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-5 w-48" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        </div>
        <div className="surface space-y-3 px-4 py-4">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
      <div className="surface flex flex-wrap items-center justify-between gap-3 px-4 py-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-10 w-44" />
      </div>
      <KpiSkeleton count={3} />
      <ChartSkeleton />
    </div>
  );
}
