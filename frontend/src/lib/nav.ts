import {
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

export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/pending", label: "Pending Replies", icon: CheckCheck },
  { href: "/knowledge-base", label: "Business Knowledge", icon: BookOpen },
  { href: "/playground", label: "Playground", icon: Sparkles },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/leads", label: "Leads", icon: Target },
  { href: "/appointments", label: "Appointments", icon: CalendarClock },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];
