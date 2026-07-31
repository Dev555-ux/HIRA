"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Bot, X } from "lucide-react";
import { useState } from "react";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { Topbar } from "@/components/layout/topbar";

function Brand({ action }: { action?: React.ReactNode }) {
  return (
    <div className="flex h-14 items-center justify-between gap-2 border-b px-5">
      <div className="flex items-center gap-2">
        <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Bot className="size-4" aria-hidden="true" />
        </div>
        <span className="text-sm font-semibold tracking-tight">HIRA</span>
      </div>
      {action}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar — flat and hairline-bordered, not detached/floating:
          Stitch's glassmorphic margin-and-blur treatment was deliberately
          rejected as dated next to Linear/Vercel's flush sidebars (see
          DEC-052). Depth instead comes from bg-elevated stepping one tone up
          from the page's bg-background — tonal layering, per Stitch's own
          elevation model, without a floating/detached shape. */}
      <aside className="hidden w-60 shrink-0 border-r bg-elevated md:flex md:flex-col">
        <Brand />
        <SidebarNav />
      </aside>

      {/* Mobile navigation — this one genuinely floats above content, so it
          earns the shadow the desktop sidebar deliberately doesn't get. */}
      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 md:hidden data-[state=open]:animate-overlay-show data-[state=closed]:animate-overlay-hide" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-elevated shadow-lg md:hidden data-[state=open]:animate-sheet-left-show data-[state=closed]:animate-sheet-left-hide">
            <Dialog.Title className="sr-only">Navigation</Dialog.Title>
            <Brand
              action={
                <Dialog.Close
                  aria-label="Close navigation"
                  className="rounded-md p-1.5 opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="size-4" aria-hidden="true" />
                </Dialog.Close>
              }
            />
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
