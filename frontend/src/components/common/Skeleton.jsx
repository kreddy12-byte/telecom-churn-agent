export default function Skeleton({ className = "h-4 w-full" }) {
  return <div className={`animate-pulse bg-slate-200 ${className}`} />;
}

export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="surface overflow-hidden">
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
