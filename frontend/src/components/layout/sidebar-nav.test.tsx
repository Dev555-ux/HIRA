import { render, screen, within } from "@testing-library/react";
import type { MouseEvent, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "@/lib/nav";
import { SidebarNav } from "./sidebar-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/inbox",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    onClick?: (e: MouseEvent) => void;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const ALL_ITEMS = navGroups.flatMap((g) => g.items);
const NAMED_GROUPS = navGroups.filter((g) => g.label !== null);

describe("SidebarNav — M15 grouping", () => {
  it("renders all 12 routes with their real hrefs, expanded", () => {
    render(<SidebarNav />);
    expect(ALL_ITEMS).toHaveLength(12);
    for (const item of ALL_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toHaveAttribute("href", item.href);
    }
  });

  it("marks only the active route's link with aria-current=page", () => {
    render(<SidebarNav />);
    expect(screen.getByRole("link", { name: "Inbox" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Escalations" })).not.toHaveAttribute("aria-current");
  });

  it("renders each named group as a real heading, announced to screen readers via role=group", () => {
    render(<SidebarNav />);
    for (const group of NAMED_GROUPS) {
      const heading = screen.getByRole("heading", { name: group.label! });
      const groupEl = screen.getByRole("group", { name: group.label! });
      expect(groupEl).toContainElement(heading);
      for (const item of group.items) {
        expect(within(groupEl).getByRole("link", { name: item.label })).toBeInTheDocument();
      }
    }
  });

  it("does not wrap the ungrouped top item (Dashboard) in a role=group", () => {
    render(<SidebarNav />);
    const dashboard = screen.getByRole("link", { name: "Dashboard" });
    expect(dashboard.closest('[role="group"]')).toBeNull();
  });

  it("collapsed: hides the visible heading text but keeps the group's accessible name", () => {
    render(<SidebarNav collapsed />);
    for (const group of NAMED_GROUPS) {
      expect(screen.queryByRole("heading", { name: group.label! })).not.toBeInTheDocument();
      expect(screen.getByRole("group", { name: group.label! })).toBeInTheDocument();
    }
  });

  it("collapsed: every route link is still accessible by its full name", () => {
    render(<SidebarNav collapsed />);
    for (const item of ALL_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("renders exactly one active-item indicator, shared across the whole nav (not one per link)", () => {
    const { container } = render(<SidebarNav />);
    const nav = screen.getByRole("navigation", { name: "Primary" });
    // The indicator is the nav's own direct aria-hidden child, not something
    // owned by any individual link — a shared element that moves, per
    // DESIGN-MOTION-001 §5.4, rather than one instance per NavLink.
    expect(nav.querySelectorAll(':scope > [aria-hidden="true"]')).toHaveLength(1);
    expect(container.querySelectorAll('a [aria-hidden="true"]')).toHaveLength(ALL_ITEMS.length);
  });
});
