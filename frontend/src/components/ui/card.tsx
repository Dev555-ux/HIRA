import * as React from "react";
import { cn } from "@/lib/utils";

// Exported so non-div elements that can't use <Card> directly (e.g. an <li>
// inside a semantic <ol>, or a <details> that needs native disclosure
// behavior) can still match its exact visual spec via `cn(cardClassName, ...)`
// instead of re-declaring the class string by hand and drifting from it.
//
// HIRA V2: no hard border on the resting state — separation now comes from
// elevation (bumped e1→e2) and the card/background tone difference instead,
// a "floating surface" rather than a boxed one. A hairline border returns at
// border/60 only where a surface needs to read as adjacent to another
// same-toned surface at rest (see interactiveClassName below, which keeps its
// own border on hover/active for the same reason).
export const cardClassName = "rounded-2xl bg-card text-card-foreground shadow-e2";

// Opt-in hover lift for clickable cards (DESIGN-MOTION-001 §5.2: one step up
// on hover, back to resting on press). Off by default so static container
// cards are unchanged — only cards that are actually interactive should move.
// Resting is e2 (see cardClassName); hover steps to e3, press settles back.
const interactiveClassName =
  "transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e3 active:translate-y-0 active:shadow-e2";

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
