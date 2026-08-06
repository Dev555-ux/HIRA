"use client";

import { Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { useAuthContext } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";

export function Topbar({
  onOpenMobileNav,
  onOpenPalette,
}: {
  onOpenMobileNav: () => void;
  onOpenPalette: () => void;
}) {
  const { mocked } = useAuthContext();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        onClick={onOpenMobileNav}
      >
        <Menu />
      </Button>
      <button
        type="button"
        onClick={onOpenPalette}
        className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm text-muted-foreground transition-colors duration-[var(--motion-fast)] hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:w-64"
      >
        <Search className="size-4 shrink-0" aria-hidden="true" />
        <span className="hidden sm:inline">Search...</span>
        <kbd className="ml-auto hidden shrink-0 items-center rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] sm:flex">
          ⌘K
        </kbd>
      </button>
      <div className="flex-1" />
      {mocked && (
        <Badge variant="warning" className="hidden sm:inline-flex">
          Mock auth
        </Badge>
      )}
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}
