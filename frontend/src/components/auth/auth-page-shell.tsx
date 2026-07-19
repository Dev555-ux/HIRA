import { Bot } from "lucide-react";
import Link from "next/link";

// Shared by /sign-in and /sign-up so the two flows are visually distinct
// before Clerk's widget (identical either way) even loads — without this,
// a first-time visitor landing on either route sees the same blank screen
// and can't tell "come back and sign in" from "start a new account" apart,
// or find a way back to the marketing site.
export function AuthPageShell({
  heading,
  subheading,
  children,
}: {
  heading: string;
  subheading: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-4">
      <Link href="/" className="flex items-center gap-2 font-semibold">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Bot className="size-4" aria-hidden="true" />
        </span>
        HIRA
      </Link>

      <div className="text-center">
        <h1 className="text-xl font-semibold tracking-tight">{heading}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">{subheading}</p>
      </div>

      {children}
    </div>
  );
}
