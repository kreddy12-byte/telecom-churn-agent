import { useEffect } from "react";
import IconButton from "./IconButton";

export default function Drawer({ title, children, onClose, side = "right" }) {
  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  const sideClass = side === "left" ? "left-0 border-r" : "right-0 border-l";

  return (
    <div className="fixed inset-0 z-40">
      <button
        type="button"
        aria-label="Close drawer"
        className="absolute inset-0 bg-ink/35 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute inset-y-0 ${sideClass} flex w-full max-w-md animate-ri-fade-in flex-col border-line-elevated bg-paper-raised shadow-elevated`}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <IconButton label="Close" variant="ghost" onClick={onClose} className="h-8 w-8">
            <span aria-hidden="true" className="text-lg leading-none">
              ×
            </span>
          </IconButton>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  );
}
