import * as React from "react";
import { cn } from "@/lib/utils";

// Exported so non-div elements that can't use <Card> directly (e.g. an <li>
// inside a semantic <ol>, or a <details> that needs native disclosure
// behavior) can still match its exact visual spec via `cn(cardClassName, ...)`
// instead of re-declaring the class string by hand and drifting from it.
export const cardClassName = "rounded-xl border bg-card text-card-foreground shadow-sm";

// Stitch: "Cards — Interaction: transition over 200ms. On hover, the shadow
// depth increases, and the border color brightens slightly." A separate
// export, not a Card prop, so only genuinely clickable cards (list rows,
// nav-like cards) opt in — a static info card must not imply it's
// interactive just because it happens to render inside <Card>.
export const interactiveCardClassName = cn(
  cardClassName,
  "cursor-pointer transition-[box-shadow,border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-ring/30 hover:shadow-md active:translate-y-0",
);

function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(cardClassName, className)} {...props} />;
}

function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("font-semibold leading-none tracking-tight", className)} {...props} />
  );
}

function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center p-6 pt-0", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
