import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const EXIT_DURATION = 260;

export function DetailDrawer({
  children,
  title,
  triggerRef,
  onClose,
}: {
  children: React.ReactNode;
  title: string;
  triggerRef?: React.RefObject<HTMLElement | null>;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  const [exiting, setExiting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const exitTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReducedMotion) {
      setMounted(true);
    } else {
      const raf = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(raf);
    }
  }, []);

  useEffect(() => {
    const el = contentRef.current?.querySelector<HTMLElement>(
      'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    el?.focus();
  }, []);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (exitTimerRef.current !== null) {
        window.clearTimeout(exitTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !exiting) {
        handleClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function handleClose() {
    if (exiting) return;
    setExiting(true);
    exitTimerRef.current = window.setTimeout(() => {
      triggerRef?.current?.focus();
      onClose();
    }, EXIT_DURATION);
  }

  return (
    <>
      <div
        className={`drawer-overlay${mounted ? " open" : ""}${exiting ? " exiting" : ""}`}
        onClick={handleClose}
      />
      <div
        className={`detail-drawer${mounted ? " open" : ""}${exiting ? " exiting" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        ref={contentRef}
      >
        <div className="drawer-header">
          <h2 id="drawer-title" className="sr-only">{title}</h2>
          <button
            className="icon-button"
            onClick={handleClose}
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>
        <div className="drawer-body">
          {children}
        </div>
      </div>
    </>
  );
}
