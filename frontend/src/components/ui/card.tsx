import * as React from "react";
import { cn } from "@/lib/utils";

// Exported so non-div elements that can't use <Card> directly (e.g. an <li>
// inside a semantic <ol>, or a <details> that needs native disclosure
// behavior) can still match its exact visual spec via `cn(cardClassName, ...)`
// instead of re-declaring the class string by hand and drifting from it.
export const cardClassName = "rounded-xl border bg-card text-card-foreground shadow-e1";

// Opt-in hover lift for clickable cards (DESIGN-MOTION-001 §5.2: E1→E2 + a 1px
// rise). Off by default so static container cards are unchanged — only cards
// that are actually interactive should move.
const interactiveClassName =
  "transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e2 active:translate-y-0 active:shadow-e1";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

function Card({ className, interactive = false, ...props }: CardProps) {
  return (
    <div
      className={cn(cardClassName, interactive && interactiveClassName, className)}
      {...props}
    />
  );
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
