import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  loading,
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  hint?: string;
  loading?: boolean;
}) {
  return (
    // IMPLEMENTATION-ROADMAP-001 M3: the hand-rolled hover (raw shadow-md,
    // a bespoke border-color fade, a 2px lift on a magic 200ms duration) is
    // replaced by Card's own `interactive` prop — the same token-driven
    // lift/shadow-e1↔e2 treatment every other interactive card in the app
    // uses, instead of a second, slightly different implementation of the
    // same idea living only here.
    <Card interactive className="group">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {loading ? (
              <Skeleton className="h-9 w-16" />
            ) : (
              // The value itself never animates (no count-up) — only its
              // one-time entrance, replacing the skeleton, gets a fade.
              <p className="animate-fade-in text-3xl font-semibold tabular-nums tracking-tight">
                {value}
              </p>
            )}
            <p className="mt-1.5 text-sm text-muted-foreground">{label}</p>
          </div>
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 transition-colors duration-200 group-hover:bg-primary/15">
            <Icon className="size-4 text-primary" />
          </div>
        </div>
        {hint && <p className="mt-3 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
