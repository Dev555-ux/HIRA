import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CalendarClock,
  Inbox,
  LayoutDashboard,
  BookOpen,
  Settings,
  Sparkles,
  Target,
  Users,
  CheckCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  /** null = rendered without a heading (Dashboard, at the top — matching
   *  DESIGN-SCREENBOOK-001 §1's own "Overview" sitting above any group). */
  label: string | null;
  items: NavItem[];
}

// IMPLEMENTATION-ROADMAP-001 M15: same 12 routes, same relative order within
// each group as the prior flat list — purely a grouping restructure, no
// destination changes. The Screenbook's own mockup names these groups
// ("Your team" / "The work" / "Your business") but its example items
// (Receptionist, To review) don't correspond to any route that exists in
// this app; the grouping below buckets the real 12 routes by what each
// screen is *for* — teaching/engaging the AI employee, the live review
// queue, and everything-else business data/config.
export const navGroups: NavGroup[] = [
  {
    label: null,
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Your team",
    items: [
      { href: "/demo", label: "Demo Chat", icon: Sparkles },
      { href: "/knowledge-base", label: "Business Knowledge", icon: BookOpen },
    ],
  },
  {
    label: "The work",
    items: [
      { href: "/inbox", label: "Inbox", icon: Inbox },
      { href: "/pending", label: "Pending Replies", icon: CheckCheck },
      { href: "/escalations", label: "Escalations", icon: AlertTriangle },
    ],
  },
  {
    label: "Your business",
    items: [
      { href: "/customers", label: "Customers", icon: Users },
      { href: "/leads", label: "Leads", icon: Target },
      { href: "/appointments", label: "Appointments", icon: CalendarClock },
      { href: "/calendar", label: "Calendar", icon: Calendar },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

// Flat view, derived — for any consumer that just needs "every route," not
// the grouping (e.g. M16's command palette, per the roadmap's own note that
// it should reuse this data rather than maintaining a second list).
export const navItems: NavItem[] = navGroups.flatMap((group) => group.items);
