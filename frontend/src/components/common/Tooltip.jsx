/**
 * Lightweight tooltip using native title + accessible description pattern.
 * Prefer for dense data UI; expand later if rich content is needed.
 */
export default function Tooltip({ label, children, className = "" }) {
  return (
    <span className={`inline-flex ${className}`} title={label} aria-label={label}>
      {children}
    </span>
  );
}
