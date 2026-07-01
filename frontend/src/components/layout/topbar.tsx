"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { useAuthContext } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";

export function Topbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
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
