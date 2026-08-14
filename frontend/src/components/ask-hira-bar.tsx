"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
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
//
// V6: audited before adding quick links below the search entry — the
// palette this button opens (`command-palette.tsx`) is fuzzy-search
// navigation over static nav items, not a conversational endpoint that can
// answer a free-text business question, and no backend endpoint exists to
// answer one. First pass phrased these as questions ("What needs my
// approval?") sitting directly under "Ask HIRA anything" — that combination
// implied an in-place conversational answer clicking through to a full page
// doesn't deliver. Re-reviewed and reworded as plain destination labels
// (never a question, never a command verb pretending an answer is coming)
// specifically so the affordance reads as "jump to a real page," matching
// what actually happens — not a fabricated Q&A engine.
//
// Sprint 84 (Dashboard Foundation): the headline above this bar had the same
// problem the V6 note above already fixed for the quick links — "Ask HIRA
// anything about your business" promised free-text conversational AI this
// bar has never delivered. Reworded to "Search HIRA," which is what the
// click actually opens. This is a copy-only fix, not a redesign: the real
// conversational assistant is a future sprint (see the approved Dashboard
// spec's §6/§12) — when it ships, it earns this headline back.
const QUICK_LINKS: { label: string; href: string }[] = [
  { label: "Pending approvals", href: "/pending" },
  { label: "Escalations", href: "/escalations" },
  { label: "Leads", href: "/leads" },
  { label: "Upcoming appointments", href: "/appointments" },
];

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
    <div
      className={cn(
        "w-full rounded-2xl border border-brand/20 bg-gradient-to-br from-brand/[0.07] via-card to-card p-6 shadow-e3 sm:p-8",
      )}
    >
      <button
        type="button"
        onClick={open}
        className={cn(
          "flex w-full items-center gap-5 text-left",
          "transition-[transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
      >
        <AIAvatar name="HIRA" size="xl" />
        <span className="min-w-0 flex-1">
          <span className="block text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            Search HIRA
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

      <div className="mt-5 border-t border-brand/10 pt-5">
        <span className="type-caption block text-muted-foreground">Jump to</span>
        <div className="mt-2 flex flex-wrap gap-2">
          {QUICK_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground shadow-e1 transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/30"
            >
              {link.label}
              <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
