import type { ReactNode } from "react";

// Sprint 66 PR-4 — presentation only. No state, no effects, no animation:
// a static neutral device bezel around whatever it's given. Kept in its
// own file, not inside signature-demo.tsx, specifically so the engine
// file's diff for this PR is composition-only (wrap DemoWidget in this) —
// easy to audit that nothing about the demo's state machine changed.
//
// Deliberately no branding on the chrome (no logo, no real clock/carrier
// text) — decorative-only elements are aria-hidden so assistive tech
// reaches straight through to the actual demo content. Shadow/radius
// reuse the same shadow-e3 + gradient-hairline-border technique already
// used for hero.tsx's GlassCard, so this reads as the same design system,
// not a new one — just a different (deliberately literal, phone-shaped)
// frame for a different section.
export function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-md rounded-[2.75rem] border border-border/60 bg-gradient-to-b from-muted/70 to-muted/30 p-2.5 shadow-e3 sm:p-3">
      <div className="overflow-hidden rounded-[2.1rem] bg-background">
        <div aria-hidden="true" className="flex flex-col items-center gap-2 px-4 pt-3">
          {/* Speaker cutout */}
          <div className="h-1.5 w-12 rounded-full bg-foreground/15" />
          {/* Decorative status bar — abstract, not a real clock/carrier readout */}
          <div className="flex w-full items-center justify-end gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-foreground/15" />
            <span className="h-1.5 w-3 rounded-full bg-foreground/15" />
          </div>
        </div>
        {/* Safe spacing: the demo content never touches the bezel or notch. */}
        <div className="p-4 sm:p-5">{children}</div>
      </div>
    </div>
  );
}
