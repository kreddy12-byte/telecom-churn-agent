import { useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  PRIMARY_NAV,
  PRODUCT,
  SYSTEM_NAV,
  isNavActive,
} from "./navigation";
import NavIcon, { ProductMark } from "./NavIcon";
import UserMenu from "./UserMenu";

function NavItem({ item, onNavigate, pathname }) {
  const active = isNavActive(item, pathname);
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`group relative flex items-center gap-3 rounded-control px-3 py-2.5 text-sm transition-colors duration-fast ease-ri focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${
        active
          ? "bg-accent-soft font-semibold text-accent"
          : "font-medium text-ink-muted hover:bg-surface-hover hover:text-ink"
      }`}
    >
      <span
        className={`absolute inset-y-1.5 left-0 w-0.5 rounded-full transition-opacity duration-fast ${
          active ? "bg-accent opacity-100" : "opacity-0"
        }`}
        aria-hidden="true"
      />
      <NavIcon
        name={item.icon}
        className={`h-4 w-4 shrink-0 ${active ? "text-accent" : "text-ink-faint group-hover:text-ink-muted"}`}
      />
      <span className="truncate">{item.label}</span>
    </NavLink>
  );
}

export default function Sidebar({
  open = false,
  onClose,
  user,
  role,
  onSignOut,
}) {
  const location = useLocation();
  const firstLinkRef = useRef(null);
  const pathname = location.pathname;

  useEffect(() => {
    if (!open) return undefined;

    function onKey(event) {
      if (event.key === "Escape") onClose?.();
    }
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Move focus into the panel for keyboard users on mobile open.
    const timer = window.setTimeout(() => {
      firstLinkRef.current?.querySelector("a")?.focus();
    }, 0);

    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
      window.clearTimeout(timer);
    };
  }, [open, onClose]);

  return (
    <>
      <button
        type="button"
        aria-label="Close navigation"
        tabIndex={open ? 0 : -1}
        className={`fixed inset-0 z-30 bg-ink/30 backdrop-blur-[2px] transition-opacity duration-ri ease-ri lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />

      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-[16.5rem] shrink-0 flex-col border-r border-line bg-paper-raised transition-transform duration-ri ease-ri lg:static lg:z-0 lg:translate-x-0 ${
          open ? "translate-x-0 shadow-elevated" : "-translate-x-full"
        }`}
      >
        <div className="relative overflow-hidden border-b border-line px-4 py-5">
          <div
            className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-accent/10 blur-3xl"
            aria-hidden="true"
          />
          <div className="relative flex items-center gap-3">
            <ProductMark />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold tracking-tight text-ink">
                {PRODUCT.name}
              </p>
              <p className="truncate text-[11px] leading-4 text-ink-muted">
                {PRODUCT.descriptor}
              </p>
            </div>
          </div>
        </div>

        <nav
          className="flex-1 space-y-6 overflow-y-auto px-3 py-4"
          aria-label="Primary"
          ref={firstLinkRef}
        >
          <div className="space-y-0.5">
            {PRIMARY_NAV.map((item) => (
              <NavItem
                key={item.to}
                item={item}
                pathname={pathname}
                onNavigate={onClose}
              />
            ))}
          </div>

          <div>
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-faint">
              System
            </p>
            <div className="space-y-0.5">
              {SYSTEM_NAV.map((item) => (
                <NavItem
                  key={item.to}
                  item={item}
                  pathname={pathname}
                  onNavigate={onClose}
                />
              ))}
            </div>
          </div>
        </nav>

        <div className="border-t border-line p-3">
          {user ? (
            <UserMenu
              user={user}
              role={role}
              onSignOut={onSignOut}
              placement="up"
              dense
              className="w-full"
            />
          ) : (
            <p className="px-2 text-[10px] uppercase tracking-[0.08em] text-ink-faint">
              Predict · Explain · Recommend · Decide
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
