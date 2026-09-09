import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

export default function UserMenu({ user, role, onSignOut }) {
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
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="flex max-w-[16rem] items-center gap-2 rounded-panel border border-line px-2 py-0.5 text-left hover:bg-slate-50"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {picture ? (
          <img
            src={picture}
            alt=""
            className="h-6 w-6 rounded-full object-cover"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent-soft text-[10px] font-semibold text-accent">
            {displayName.slice(0, 1).toUpperCase()}
          </span>
        )}
        <span className="min-w-0">
          <span className="block truncate font-medium text-ink">{displayName}</span>
          {email ? <span className="block truncate text-[10px] text-ink-faint">{email}</span> : null}
        </span>
        {role ? (
          <span className="shrink-0 rounded-panel border border-line px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink">
            {role}
          </span>
        ) : null}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-44 border border-line bg-white py-1 shadow-card"
        >
          <Link
            role="menuitem"
            to="/profile"
            className="block px-3 py-1.5 text-sm text-ink hover:bg-slate-50"
            onClick={() => setOpen(false)}
          >
            Profile
          </Link>
          <Link
            role="menuitem"
            to="/account"
            className="block px-3 py-1.5 text-sm text-ink hover:bg-slate-50"
            onClick={() => setOpen(false)}
          >
            Account
          </Link>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-sm text-ink hover:bg-slate-50"
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
