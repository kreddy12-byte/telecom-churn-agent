import { NavLink } from "react-router-dom";

const PRIMARY = [
  { to: "/", label: "Overview", end: true },
  { to: "/customers", label: "Customers" },
  { to: "/actions", label: "Retention actions" },
];

const SYSTEM = [{ to: "/model", label: "Model information" }];

function Item({ to, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `block border-l-2 px-3 py-2 text-sm ${
          isActive
            ? "border-accent bg-accent-soft font-semibold text-accent"
            : "border-transparent text-ink-muted hover:bg-slate-50 hover:text-ink"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-white">
      <div className="border-b border-line px-4 py-4">
        <p className="text-[13px] font-semibold tracking-tight text-ink">
          Retention Intelligence
        </p>
        <p className="mt-0.5 text-[11px] leading-4 text-ink-muted">
          Telecom churn decision support
        </p>
      </div>
      <nav className="flex-1 py-3" aria-label="Primary">
        {PRIMARY.map((item) => (
          <Item key={item.to} {...item} />
        ))}
        <p className="mb-1 mt-6 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
          System
        </p>
        {SYSTEM.map((item) => (
          <Item key={item.to} {...item} />
        ))}
      </nav>
    </aside>
  );
}
