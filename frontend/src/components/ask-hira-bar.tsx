"use client";

import { ArrowRight } from "lucide-react";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { cardClassName } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Home's command centre entry point (HIRA v2 Phase 4). Reuses the existing
// global command palette (AppShell + CommandPalette, already wired to
// Cmd/Ctrl+K) instead of building a second AI interface — clicking this
// dispatches the same keyboard event AppShell's own global listener already
// handles, so there is exactly one palette implementation and one open/close
// state machine. App Shell is explicitly out of scope for this phase, so
// this reaches the palette through its existing public surface (the
// shortcut) rather than adding a prop/context to AppShell itself.
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
        cardClassName,
        "flex w-full items-center gap-4 p-5 text-left transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <AIAvatar name="HIRA" size="lg" />
      <span className="min-w-0 flex-1">
        <span className="block text-base font-medium text-foreground">
          Ask HIRA anything about your business
        </span>
        <span className="block text-sm text-muted-foreground">
          Search customers, jump to a page, or find what you need
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-2 text-muted-foreground">
        <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] sm:block">
          ⌘K
        </kbd>
        <ArrowRight className="size-4" aria-hidden="true" />
      </span>
    </button>
  );
}
