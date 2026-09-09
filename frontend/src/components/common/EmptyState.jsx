export default function EmptyState({ title, body }) {
  return (
    <div className="surface px-5 py-8 text-center">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {body ? <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-ink-muted">{body}</p> : null}
    </div>
  );
}
