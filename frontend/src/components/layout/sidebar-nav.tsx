"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { navGroups, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

function NavLink({
  item,
  collapsed,
  active,
  onNavigate,
  linkRef,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
  onNavigate?: () => void;
  linkRef: (node: HTMLAnchorElement | null) => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      ref={linkRef}
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      // Native tooltip is the icon-only affordance when collapsed; the
      // label stays the accessible name via the sr-only span below.
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-[var(--motion-fast)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        collapsed && "justify-center",
        active
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
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
  const navRef = useRef<HTMLElement>(null);
  const linkNodes = useRef(new Map<string, HTMLAnchorElement>());
  // DESIGN-MOTION-001 §5.4: "a single pill/left-bar that slides from the old
  // active item to the new one — one indicator that moves, never one that
  // fades out here and in there." Starts null on both server and client (a
  // real DOM measurement can only happen after mount) so there's nothing to
  // mismatch on hydration; the effect below measures and positions it.
  const [indicatorTop, setIndicatorTop] = useState<number | null>(null);

  useEffect(() => {
    const nav = navRef.current;
    const active = [...linkNodes.current.entries()].find(
      ([href]) => pathname === href || pathname.startsWith(`${href}/`),
    )?.[1];
    if (!nav || !active) {
      setIndicatorTop(null);
      return;
    }
    const navTop = nav.getBoundingClientRect().top;
    const linkRect = active.getBoundingClientRect();
    // Centers a fixed 20px (h-5) bar on the active row, matching the old
    // per-item indicator's own size — only how it moves between rows changed.
    setIndicatorTop(linkRect.top - navTop + linkRect.height / 2 - 10);
  }, [pathname, collapsed]);

  return (
    <nav ref={navRef} className="relative flex flex-col gap-4 px-3 py-4" aria-label="Primary">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-0 h-5 w-0.5 rounded-full bg-primary transition-[transform,opacity] duration-[var(--motion-slow)] ease-[var(--ease-in-out-quart)]"
        style={{
          transform: `translateY(${indicatorTop ?? 0}px)`,
          opacity: indicatorTop === null ? 0 : 1,
        }}
      />
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
              linkRef={(node) => {
                if (node) linkNodes.current.set(item.href, node);
                else linkNodes.current.delete(item.href);
              }}
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
