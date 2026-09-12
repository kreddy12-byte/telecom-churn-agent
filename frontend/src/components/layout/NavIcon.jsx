const STROKE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export default function NavIcon({ name, className = "h-4 w-4" }) {
  const props = { className, viewBox: "0 0 24 24", "aria-hidden": true, ...STROKE };

  switch (name) {
    case "overview":
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "customers":
      return (
        <svg {...props}>
          <circle cx="9" cy="8" r="3.25" />
          <path d="M3.5 19c.8-3.2 2.9-5 5.5-5s4.7 1.8 5.5 5" />
          <circle cx="17" cy="9" r="2.25" />
          <path d="M16 14.2c2 .4 3.5 1.8 4 4.8" />
        </svg>
      );
    case "actions":
      return (
        <svg {...props}>
          <path d="M5 6h14M5 12h10M5 18h12" />
          <circle cx="18" cy="12" r="1.5" fill="currentColor" stroke="none" />
        </svg>
      );
    case "batch":
      return (
        <svg {...props}>
          <path d="M4 7h16v3H4zM4 14h16v3H4z" />
          <path d="M8 7V4h8v3M8 20v-3h8v3" />
        </svg>
      );
    case "model":
      return (
        <svg {...props}>
          <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" />
          <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
        </svg>
      );
    case "account":
      return (
        <svg {...props}>
          <circle cx="12" cy="8" r="3.25" />
          <path d="M5 19c1.2-3.5 3.6-5.2 7-5.2s5.8 1.7 7 5.2" />
        </svg>
      );
    default:
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="7" />
        </svg>
      );
  }
}

export function ProductMark({ className = "h-8 w-8" }) {
  return (
    <span
      className={`relative inline-flex items-center justify-center rounded-control bg-accent-soft text-[11px] font-bold tracking-tight text-accent ring-1 ring-accent/25 ${className}`}
      aria-hidden="true"
    >
      <span
        className="pointer-events-none absolute inset-0 rounded-control bg-gradient-to-br from-accent/30 to-accent-secondary/20 opacity-80"
        aria-hidden="true"
      />
      <span className="relative">CI</span>
    </span>
  );
}
