const VARIANTS = {
  primary:
    "bg-accent text-ink-inverse shadow-sm hover:bg-accent-hover hover:shadow-glow active:scale-[0.98] disabled:bg-surface-interactive disabled:text-ink-disabled disabled:shadow-none disabled:active:scale-100",
  secondary:
    "border border-line bg-surface-interactive text-ink hover:border-line-elevated hover:bg-surface-hover active:scale-[0.98] disabled:text-ink-disabled disabled:active:scale-100",
  danger:
    "border border-danger/40 bg-danger-soft text-danger hover:bg-danger/20 active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100",
  ghost:
    "text-accent hover:bg-accent-soft active:scale-[0.98] disabled:text-ink-disabled disabled:active:scale-100",
};

const SIZES = {
  sm: "px-2.5 py-1 text-xs",
  md: "px-3.5 py-1.5 text-sm",
  lg: "px-4 py-2.5 text-sm",
};

export default function Button({
  children,
  variant = "secondary",
  size = "md",
  type = "button",
  className = "",
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-control font-medium transition-all duration-fast ease-ri focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${VARIANTS[variant] || VARIANTS.secondary} ${SIZES[size] || SIZES.md} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
