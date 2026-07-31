"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Bot, PanelLeft, PanelLeftClose, X } from "lucide-react";
import { useState } from "react";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { Topbar } from "@/components/layout/topbar";
import { cn } from "@/lib/utils";

function Brand({ collapsed = false, action }: { collapsed?: boolean; action?: React.ReactNode }) {
  return (
    <div
      className={cn(
        "flex h-14 items-center border-b",
        collapsed ? "justify-center px-2" : "justify-between gap-2 px-5",
      )}
    >
      <div className="flex items-center gap-2">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Bot className="size-4" aria-hidden="true" />
        </div>
        {!collapsed && <span className="text-sm font-semibold tracking-tight">HIRA</span>}
      </div>
      {action}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  // Desktop collapse. In-memory: the (dashboard) layout is preserved across
  // route changes, so this survives navigation within a session (it resets on a
  // hard reload — cookie persistence is a deliberate PR4 follow-up, kept out
  // here to avoid any SSR/hydration risk).
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Keyboard/screen-reader users can jump straight to content, past the nav. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[var(--z-max)] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground focus:shadow-e3 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>

      {/* Desktop sidebar — collapsible. Width animates on the slow motion token
          (DESIGN-MOTION-001 §5.4); the reduced-motion guard collapses it to
          instant. */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r transition-[width] duration-[var(--motion-slow)] ease-[var(--ease-in-out-quart)] md:flex",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <Brand collapsed={collapsed} />
        <div className="flex-1 overflow-y-auto overscroll-contain">
          <SidebarNav collapsed={collapsed} />
        </div>
        <div className="border-t p-3">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors duration-[var(--motion-fast)] hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed && "justify-center",
            )}
          >
            {collapsed ? (
              <PanelLeft className="size-4" aria-hidden="true" />
            ) : (
              <>
                <PanelLeftClose className="size-4" aria-hidden="true" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Mobile navigation — drawer/sheet via the shared overlay/sheet motion
          primitives. Radix Dialog handles focus trap + Esc + scroll lock. */}
      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-[var(--z-overlay)] bg-black/50 backdrop-blur-backdrop-sm md:hidden data-[state=open]:animate-overlay-show data-[state=closed]:animate-overlay-hide" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-[var(--z-dialog)] flex w-64 flex-col border-r bg-background shadow-e3 md:hidden data-[state=open]:animate-sheet-left-show data-[state=closed]:animate-sheet-left-hide">
            <Dialog.Title className="sr-only">Navigation</Dialog.Title>
            <Brand
              action={
                <Dialog.Close
                  aria-label="Close navigation"
                  className="rounded-md p-1.5 opacity-70 transition-opacity duration-[var(--motion-fast)] hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="size-4" aria-hidden="true" />
                </Dialog.Close>
              }
            />
            <div className="flex-1 overflow-y-auto overscroll-contain">
              <SidebarNav onNavigate={() => setMobileOpen(false)} />
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setMobileOpen(true)} />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 p-4 focus:outline-none sm:p-6 lg:p-8"
        >
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
