const VARIANTS = {
  primary:
    "bg-accent text-white hover:bg-accent-hover disabled:bg-slate-300 disabled:text-slate-600",
  secondary:
    "border border-line bg-white text-ink hover:bg-slate-50 disabled:text-ink-faint",
  danger:
    "border border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100 disabled:opacity-50",
  ghost: "text-accent hover:underline disabled:text-ink-faint",
};

export default function Button({
  children,
  variant = "secondary",
  type = "button",
  className = "",
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-panel px-3 py-1.5 text-sm font-medium transition-colors ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
