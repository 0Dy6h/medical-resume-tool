import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type ToastTone = "success" | "error" | "info";

type ToastItem = {
  id: number;
  tone: ToastTone;
  message: string;
  exiting: boolean;
};

type ToastApi = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

const TOAST_DURATION = 3500;
const EXIT_DURATION = 120;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const autoTimersRef = useRef<Map<number, number>>(new Map());
  const exitTimersRef = useRef<Map<number, number>>(new Map());

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    autoTimersRef.current.delete(id);
    exitTimersRef.current.delete(id);
  }, []);

  const startExit = useCallback((id: number) => {
    // Clear any auto-dismiss timer that may still be running
    const autoTimer = autoTimersRef.current.get(id);
    if (autoTimer !== undefined) {
      window.clearTimeout(autoTimer);
      autoTimersRef.current.delete(id);
    }
    // Don't double-trigger exit
    if (exitTimersRef.current.has(id)) return;

    setToasts((current) =>
      current.map((toast) => (toast.id === id ? { ...toast, exiting: true } : toast))
    );

    const timer = window.setTimeout(() => {
      remove(id);
    }, EXIT_DURATION);
    exitTimersRef.current.set(id, timer);
  }, [remove]);

  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current, { id, tone, message, exiting: false }]);
      const autoTimer = window.setTimeout(() => startExit(id), TOAST_DURATION);
      autoTimersRef.current.set(id, autoTimer);
    },
    [startExit]
  );

  useEffect(() => {
    const autoTimers = autoTimersRef.current;
    const exitTimers = exitTimersRef.current;
    return () => {
      autoTimers.forEach((timer) => window.clearTimeout(timer));
      autoTimers.clear();
      exitTimers.forEach((timer) => window.clearTimeout(timer));
      exitTimers.clear();
    };
  }, []);

  const api: ToastApi = {
    success: (message) => push("success", message),
    error: (message) => push("error", message),
    info: (message) => push("info", message)
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div
            className={`toast ${toast.tone}${toast.exiting ? " exiting" : ""}`}
            key={toast.id}
            onClick={() => startExit(toast.id)}
            role="status"
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
