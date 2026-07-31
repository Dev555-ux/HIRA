"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navItems } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function SidebarNav({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 px-3 py-4" aria-label="Primary">
      {navItems.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            // Native tooltip is the icon-only affordance when collapsed; the
            // label stays the accessible name via the sr-only span below.
            title={collapsed ? item.label : undefined}
            className={cn(
              "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-[var(--motion-fast)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed && "justify-center",
              active
                ? "bg-secondary text-secondary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {/* Active left-bar indicator (DESIGN-MOTION-001 §5.4). */}
            <span
              aria-hidden="true"
              className={cn(
                "absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary transition-opacity duration-[var(--motion-fast)]",
                active ? "opacity-100" : "opacity-0",
              )}
            />
            <Icon className="size-4 shrink-0" aria-hidden="true" />
            {/* Kept in the accessibility tree even when collapsed, so the icon-
                only link still has a name for screen readers. */}
            <span className={cn(collapsed && "sr-only")}>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
