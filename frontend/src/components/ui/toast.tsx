"use client";

import { CheckCircle2, X, XCircle } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: "default" | "success" | "destructive";
}

interface ToastItem extends ToastOptions {
  id: string;
  leaving: boolean;
}

interface ToastContextValue {
  toast: (options: ToastOptions) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

const TOAST_DURATION_MS = 5000;
// Must match toast-hide's keyframe duration in globals.css — the toast is
// only removed from the DOM once its exit animation has actually finished.
const TOAST_EXIT_ANIMATION_MS = 150;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const remove = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const dismiss = React.useCallback(
    (id: string) => {
      setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
      setTimeout(() => remove(id), TOAST_EXIT_ANIMATION_MS);
    },
    [remove],
  );

  const toast = React.useCallback(
    (options: ToastOptions) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { ...options, id, leaving: false }]);
      setTimeout(() => dismiss(id), TOAST_DURATION_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const Icon =
    toast.variant === "destructive" ? XCircle : toast.variant === "success" ? CheckCircle2 : null;

  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-3 rounded-xl border bg-card p-4 text-card-foreground shadow-e3",
        toast.leaving ? "animate-toast-hide" : "animate-toast-show",
        toast.variant === "success" && "border-success/30",
        toast.variant === "destructive" && "border-destructive/30",
      )}
    >
      {Icon && (
        <Icon
          className={cn(
            "mt-0.5 size-5 shrink-0",
            toast.variant === "success" && "text-success",
            toast.variant === "destructive" && "text-destructive",
          )}
        />
      )}
      <div className="flex-1 space-y-1">
        <p className="text-sm font-semibold">{toast.title}</p>
        {toast.description && (
          <p className="whitespace-pre-line text-sm text-muted-foreground">
            {toast.description}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="rounded-md text-muted-foreground opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}
