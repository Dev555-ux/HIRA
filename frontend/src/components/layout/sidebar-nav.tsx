"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { navGroups, type NavItem } from "@/lib/nav";
import { Tooltip } from "@/components/ui/tooltip";
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
  const link = (
    <Link
      ref={linkRef}
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-[color,background-color,transform,box-shadow] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:shadow-e1 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        collapsed && "justify-center",
        active
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      <Icon
        className="size-4 shrink-0 transition-transform duration-[var(--motion-fast)] ease-[var(--ease-out-quart)] group-hover:translate-x-0.5 group-hover:scale-110 group-active:scale-95"
        aria-hidden="true"
      />
      {/* max-w/margin/opacity (not sr-only, not a `gap` on the row — gap
          doesn't shrink away with this element, which would leave the icon
          permanently off-center when collapsed) so collapse is a fade+clip
          in step with the sidebar's own width transition, not an instant
          snap. Still fully in the accessibility tree either way — opacity
          and max-width, unlike display/visibility, never remove a node
          from it. */}
      <span
        className={cn(
          "overflow-hidden whitespace-nowrap transition-[opacity,max-width,margin-left] duration-[var(--motion-slow)] ease-[var(--ease-in-out-quart)]",
          collapsed ? "ml-0 max-w-0 opacity-0" : "ml-3 max-w-[10rem] opacity-100 delay-[190ms]",
        )}
      >
        {item.label}
      </span>
    </Link>
  );
  // The tooltip is the icon-only affordance when collapsed (DESIGN-MOTION-001
  // §10.30: open-delay + warm-window, already built) — replaces the old
  // native `title` attribute, which had no styling or timing control.
  return collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
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
  const indicatorRef = useRef<HTMLSpanElement>(null);
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

    // §3.3 confidence spring on arrival: the slide itself is the CSS
    // `transition` below (a spring-*curve* would fight the transition), so
    // the landing bounce is a separate, imperatively-restarted keyframe
    // animation layered on top — restarting a CSS animation via className
    // alone doesn't work unless the class is removed, reflowed, and
    // re-added, since React re-rendering the same class string is a no-op
    // to the browser's animation engine.
    const el = indicatorRef.current;
    if (el) {
      el.classList.remove("animate-spring-settle");
      void el.offsetWidth;
      el.classList.add("animate-spring-settle");
    }
  }, [pathname, collapsed]);

  return (
    <nav ref={navRef} className="relative flex flex-col gap-6 px-3 py-4" aria-label="Primary">
      <span
        ref={indicatorRef}
        aria-hidden="true"
        // top-0 anchors this to the nav's own top edge — without it, the
        // absolutely-positioned span falls back to its in-flow static
        // position (after the nav's py-4 padding), and the translateY math
        // below (which assumes a top-0px baseline) lands 16px+ too low.
        // The glow (§7 "active-state glow") rides on the same brand token
        // as the bar itself, so it stays in sync across light/dark without
        // a second hand-picked color.
        className="pointer-events-none absolute left-0 top-0 h-5 w-0.5 rounded-full bg-brand shadow-[0_0_8px_1px_var(--brand-glow)] transition-[transform,opacity] duration-[var(--motion-slow)] ease-[var(--ease-in-out-quart)]"
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
