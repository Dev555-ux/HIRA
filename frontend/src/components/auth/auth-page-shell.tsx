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

      {/* T5.2 — Clerk renders client-side, so without a reservation the widget
          pops in and drags the centred stack with it: measured CLS 0.186 on
          /sign-up at 390. The height is the taller of the two widgets at each
          breakpoint, measured on a real Clerk instance (.cl-rootBox):
          sign-in 488 at both widths; sign-up 570 at 1440, 588 at 390. One
          shared shell serves both routes, so both reserve the larger value.
          Sized, not full-width, so it stays a centred flex item and the
          layout is otherwise untouched. */}
      <div className="min-h-[588px] lg:min-h-[570px]">{children}</div>
    </div>
  );
}
