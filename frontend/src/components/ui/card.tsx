import * as React from "react";
import { cn } from "@/lib/utils";

// Exported so non-div elements that can't use <Card> directly (e.g. an <li>
// inside a semantic <ol>, or a <details> that needs native disclosure
// behavior) can still match its exact visual spec via `cn(cardClassName, ...)`
// instead of re-declaring the class string by hand and drifting from it.
export const cardClassName = "rounded-xl border bg-card text-card-foreground shadow-sm";

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
