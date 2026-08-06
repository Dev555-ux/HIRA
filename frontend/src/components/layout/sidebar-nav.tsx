"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId } from "react";
import { navGroups, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

function NavLink({ item, collapsed, active, onNavigate }: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
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
}

export function SidebarNav({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const headingIdBase = useId();

  return (
    <nav className="flex flex-col gap-4 px-3 py-4" aria-label="Primary">
      {navGroups.map((group, i) => {
        const headingId = `${headingIdBase}-${i}`;
        const links = group.items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <NavLink
              key={item.href}
              item={item}
              collapsed={collapsed}
              active={active}
              onNavigate={onNavigate}
            />
          );
        });

        // The ungrouped top item (Dashboard) never gets a heading. Every
        // other group keeps its own tight gap-1 between links regardless of
        // collapsed state — only the heading disappears when collapsed
        // (no room, and an icon-only label to nobody isn't meaningful); the
        // gap-4 between groups still reads as a grouping signal on its own.
        if (group.label === null) {
          return (
            <div key={i} className="flex flex-col gap-1">
              {links}
            </div>
          );
        }

        return (
          <div
            key={i}
            role="group"
            aria-labelledby={collapsed ? undefined : headingId}
            aria-label={collapsed ? group.label : undefined}
            className="flex flex-col gap-1"
          >
            {!collapsed && (
              <h3
                id={headingId}
                className="px-3 pb-1 type-caption font-medium uppercase tracking-wide text-muted-foreground"
              >
                {group.label}
              </h3>
            )}
            {links}
          </div>
        );
      })}
    </nav>
  );
}
