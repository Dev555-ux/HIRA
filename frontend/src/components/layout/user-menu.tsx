"use client";

import { LogOut, User as UserIcon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuthContext } from "@/lib/auth-context";

export function UserMenu() {
  const { user, mocked, signOut, openProfile } = useAuthContext();
  const initials = (user?.name ?? "U")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        // Tinted, not solid, brand fill (bg-primary/10 vs. Demo Chat's
        // solid bg-primary assistant avatar) — a user's own identity marker
        // isn't a primary action, and full-strength brand here would
        // compete with the one thing it's meant to be reserved for.
        className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary transition-colors hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Open user menu"
      >
        {initials}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>
          <div className="flex flex-col">
            <span>{user?.name ?? "User"}</span>
            <span className="text-xs font-normal text-muted-foreground">
              {user?.email}
            </span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={openProfile}>
          <UserIcon className="size-4" /> Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => void signOut()}>
          <LogOut className="size-4" />
          {mocked ? "Sign out (mock)" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
