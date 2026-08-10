"use client";

import { ArrowRight } from "lucide-react";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { cn } from "@/lib/utils";

// Home's command centre entry point (HIRA v2 Phase 4). Reuses the existing
// global command palette (AppShell + CommandPalette, already wired to
// Cmd/Ctrl+K) instead of building a second AI interface — clicking this
// dispatches the same keyboard event AppShell's own global listener already
// handles, so there is exactly one palette implementation and one open/close
// state machine. App Shell is explicitly out of scope for this phase, so
// this reaches the palette through its existing public surface (the
// shortcut) rather than adding a prop/context to AppShell itself.
//
// HIRA V2: deliberately NOT built on cardClassName — the audit that led to
// this re-skin found this bar reading as "one more generic card," which
// undersold its role as the page's primary interaction. It gets its own
// elevated, brand-tinted surface instead, at e3 (a step above the resting
// cards around it) so it visually leads the page rather than sitting in the
// stack with everything else.
export function AskHiraBar() {
  function open() {
    const isMac =
      typeof navigator !== "undefined" && navigator.platform.toLowerCase().includes("mac");
    window.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        metaKey: isMac,
        ctrlKey: !isMac,
        bubbles: true,
      }),
    );
  }

  return (
    <button
      type="button"
      onClick={open}
      className={cn(
        "flex w-full items-center gap-5 rounded-2xl border border-brand/20 bg-gradient-to-br from-brand/[0.07] via-card to-card p-6 text-left shadow-e3 sm:p-8",
        "transition-[box-shadow,transform,border-color] duration-[var(--motion-fast)] ease-[var(--ease-standard)]",
        "hover:-translate-y-px hover:border-brand/35 hover:shadow-e4",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      )}
    >
      <AIAvatar name="HIRA" size="xl" />
      <span className="min-w-0 flex-1">
        <span className="block text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
          Ask HIRA anything about your business
        </span>
        <span className="mt-1 block text-sm text-muted-foreground">
          Search customers, jump to a page, or find what you need
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-2 text-muted-foreground">
        <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] sm:block">
          ⌘K
        </kbd>
        <ArrowRight className="size-5" aria-hidden="true" />
      </span>
    </button>
  );
}
