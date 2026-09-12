import { Children, cloneElement, isValidElement, useState } from "react";

export function Tabs({ children, defaultValue, value, onChange, className = "" }) {
  const items = Children.toArray(children).filter(isValidElement);
  const first = items[0]?.props?.value;
  const [internal, setInternal] = useState(defaultValue || first);
  const active = value ?? internal;

  function select(next) {
    if (value === undefined) setInternal(next);
    onChange?.(next);
  }

  return (
    <div className={className}>
      <div role="tablist" className="mb-4 flex flex-wrap gap-1 border-b border-line pb-px">
        {items.map((child) => {
          const selected = child.props.value === active;
          return (
            <button
              key={child.props.value}
              type="button"
              role="tab"
              aria-selected={selected}
              className={`rounded-t-control px-3 py-2 text-sm font-medium transition-colors duration-fast ${
                selected
                  ? "border-b-2 border-accent text-accent"
                  : "text-ink-muted hover:text-ink"
              }`}
              onClick={() => select(child.props.value)}
            >
              {child.props.label}
            </button>
          );
        })}
      </div>
      {items.map((child) =>
        child.props.value === active
          ? cloneElement(child, { key: child.props.value, active: true })
          : null
      )}
    </div>
  );
}

export function TabPanel({ children, active }) {
  if (!active) return null;
  return (
    <div role="tabpanel" className="ri-enter">
      {children}
    </div>
  );
}
