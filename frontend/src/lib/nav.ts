import {
  BarChart3,
  Inbox,
  LayoutDashboard,
  BookOpen,
  Settings,
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
  { href: "/knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];
