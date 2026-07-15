import { useEffect, ReactNode } from "react";
import ReactDOM from "react-dom";
import { X } from "lucide-react";

interface FullScreenModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  headerActions?: ReactNode;
  children: ReactNode;
}

export function FullScreenModal({ open, onClose, title, headerActions, children }: FullScreenModalProps) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 flex flex-col bg-background"
      style={{ zIndex: 40 }}
    >
      {/* Backdrop overlay (for click-outside close) */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal panel */}
      <div className="relative flex flex-col w-full h-full bg-background" style={{ zIndex: 1 }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0 bg-background">
          <span className="text-lg font-bold text-foreground">{title}</span>
          <div className="flex items-center gap-3">
            {headerActions}
            <button
              onClick={onClose}
              className="p-2 rounded-[4px] hover:bg-muted transition-colors"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
