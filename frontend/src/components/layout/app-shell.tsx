"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Bot, X } from "lucide-react";
import { useState } from "react";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { Topbar } from "@/components/layout/topbar";

function Brand() {
  return (
    <div className="flex h-14 items-center gap-2 border-b px-5">
      <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Bot className="size-4" />
      </div>
      <span className="text-sm font-semibold tracking-tight">HIRA</span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r md:flex md:flex-col">
        <Brand />
        <SidebarNav />
      </aside>

      {/* Mobile navigation */}
      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 md:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-background md:hidden">
            <Dialog.Title className="sr-only">Navigation</Dialog.Title>
            <div className="flex items-center justify-between border-b px-5 h-14">
              <span className="text-sm font-semibold">HIRA</span>
              <Dialog.Close aria-label="Close navigation">
                <X className="size-5" />
              </Dialog.Close>
            </div>
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
