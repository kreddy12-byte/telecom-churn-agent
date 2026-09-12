import { useEffect } from "react";
import IconButton from "./IconButton";

export default function Modal({ title, children, onClose }) {
  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-ink/35 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="relative z-10 w-full max-w-lg animate-ri-scale-in rounded-sheet border border-line-elevated bg-paper-raised p-5 shadow-elevated"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="dialog-title" className="text-base font-semibold tracking-tight text-ink">
            {title}
          </h2>
          <IconButton label="Close" variant="ghost" onClick={onClose} className="h-8 w-8">
            <span aria-hidden="true" className="text-lg leading-none">
              ×
            </span>
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}
