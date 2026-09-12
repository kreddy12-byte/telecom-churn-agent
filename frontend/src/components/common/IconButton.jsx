const VARIANTS = {
  default:
    "border-line bg-surface-interactive text-ink-muted hover:border-line-elevated hover:bg-surface-hover hover:text-ink",
  ghost: "text-ink-muted hover:bg-surface-hover hover:text-ink",
  danger: "border-danger/30 bg-danger-soft text-danger hover:bg-danger/20",
};

export default function IconButton({
  children,
  label,
  variant = "default",
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-control border transition-colors duration-fast ease-ri focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${VARIANTS[variant] || VARIANTS.default} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
