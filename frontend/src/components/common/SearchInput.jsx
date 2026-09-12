export default function SearchInput({ className = "", ...props }) {
  return (
    <div className={`relative ${className}`}>
      <span
        className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-faint"
        aria-hidden="true"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" strokeLinecap="round" />
        </svg>
      </span>
      <input className="field-input pl-9" type="search" {...props} />
    </div>
  );
}
