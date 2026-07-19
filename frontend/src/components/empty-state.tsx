import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed py-16 px-6 text-center",
        className,
      )}
    >
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-muted">
        <Icon className="size-6 text-muted-foreground" />
      </div>
      {/* h2, not h3: this renders directly under each page's own h1 with no
          guaranteed h2 in between (e.g. Demo Chat, Customers, Leads,
          Analytics have no section headings) — h3 here would skip a level
          for exactly those pages. Pages that do have their own h2 sections
          (Dashboard, Settings) just end up with a sibling h2, which is a
          normal, valid heading structure, not a second violation. */}
      <h2 className="text-sm font-semibold">{title}</h2>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
