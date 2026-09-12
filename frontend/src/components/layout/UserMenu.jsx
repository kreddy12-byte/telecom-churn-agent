import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Badge from "../common/Badge";

function Avatar({ picture, name }) {
  if (picture) {
    return (
      <img
        src={picture}
        alt=""
        className="h-8 w-8 rounded-full object-cover ring-1 ring-line"
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent ring-1 ring-accent/20">
      {(name || "?").slice(0, 1).toUpperCase()}
    </span>
  );
}

export default function UserMenu({
  user,
  role,
  onSignOut,
  placement = "down",
  dense = false,
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const displayName = user?.name || user?.email || "Signed in";
  const email = user?.email || "";
  const picture = user?.picture;

  useEffect(() => {
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const menuPosition =
    placement === "up"
      ? "bottom-full mb-2 left-0 right-0"
      : "top-full right-0 mt-2 w-52";

  return (
    <div className={`relative ${className}`} ref={rootRef}>
      <button
        type="button"
        className={`flex w-full items-center gap-2.5 rounded-control border border-line bg-surface-muted text-left transition-colors duration-fast hover:border-line-elevated hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${
          dense ? "px-2 py-1.5" : "px-2.5 py-1.5"
        }`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar picture={picture} name={displayName} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-ink">{displayName}</span>
          {email ? (
            <span className="block truncate text-[10px] text-ink-faint">{email}</span>
          ) : null}
        </span>
        {role ? (
          <Badge tone="accent" className="shrink-0">
            {role}
          </Badge>
        ) : null}
        <span className="shrink-0 text-ink-faint" aria-hidden="true">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d={placement === "up" ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>

      {open ? (
        <div
          role="menu"
          className={`absolute z-30 overflow-hidden rounded-panel border border-line-elevated bg-paper-raised py-1 shadow-elevated animate-ri-scale-in ${menuPosition}`}
        >
          <div className="border-b border-line px-3 py-2.5">
            <p className="truncate text-xs font-semibold text-ink">{displayName}</p>
            {email ? <p className="truncate text-[11px] text-ink-faint">{email}</p> : null}
            {role ? (
              <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-accent">
                {role}
              </p>
            ) : null}
          </div>
          <Link
            role="menuitem"
            to="/profile"
            className="block px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            onClick={() => setOpen(false)}
          >
            Profile
          </Link>
          <Link
            role="menuitem"
            to="/account"
            className="block px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            onClick={() => setOpen(false)}
          >
            Account
          </Link>
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-2 text-left text-sm text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
