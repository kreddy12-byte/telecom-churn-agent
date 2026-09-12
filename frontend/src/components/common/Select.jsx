export default function Select({ className = "", children, ...props }) {
  return (
    <div className={`relative ${className}`}>
      <select className="field-select" {...props}>
        {children}
      </select>
      <span
        className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-ink-faint"
        aria-hidden="true"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </div>
  );
}
