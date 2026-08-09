import { cva, type VariantProps } from "class-variance-authority";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

// A static, non-dismissible banner — the "this page/section has something to
// tell you" primitive. Distinct from Toast (transient, corner-anchored,
// self-dismissing): an Alert stays in flow with the content it's about, for
// as long as the condition it describes is true. Same icon+title+description
// shape as Toast so the two read as one family, never two competing patterns.
const alertVariants = cva(
  "flex items-start gap-3 rounded-xl border p-4 text-sm",
  {
    variants: {
      variant: {
        default: "border-border bg-card text-card-foreground",
        info: "border-border bg-muted text-foreground",
        success: "border-success/30 bg-success/10 text-foreground",
        warning: "border-warning/30 bg-warning/10 text-foreground",
        destructive: "border-destructive/30 bg-destructive/10 text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

const ICON: Record<NonNullable<VariantProps<typeof alertVariants>["variant"]>, React.ElementType | null> = {
  default: null,
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  destructive: XCircle,
};

const ICON_COLOR: Record<NonNullable<VariantProps<typeof alertVariants>["variant"]>, string> = {
  default: "",
  info: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
};

export interface AlertProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title">,
    VariantProps<typeof alertVariants> {
  title?: React.ReactNode;
  /** Override the variant's default icon; pass `false` to render none. */
  icon?: React.ReactNode | false;
}

function Alert({ className, variant = "default", title, icon, children, ...props }: AlertProps) {
  const v = variant ?? "default";
  const Icon = ICON[v];
  return (
    <div
      role={v === "destructive" || v === "warning" ? "alert" : "status"}
      className={cn(alertVariants({ variant: v }), className)}
      {...props}
    >
      {icon !== false && (icon ?? (Icon && <Icon className={cn("mt-0.5 size-4 shrink-0", ICON_COLOR[v])} aria-hidden />))}
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-semibold leading-tight">{title}</p>}
        {children && <div className="text-muted-foreground [&:first-child]:text-foreground">{children}</div>}
      </div>
    </div>
  );
}

export { Alert, alertVariants };
