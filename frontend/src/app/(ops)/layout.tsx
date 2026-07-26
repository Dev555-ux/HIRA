import { ShieldAlert } from "lucide-react";

// Sprint 73: deliberately its own route group, not nested under (dashboard)
// — no AppShell, no customer nav, no onboarding-status gate (irrelevant
// here; the founder's own authorization is enforced by the API itself, see
// useFounderOverview/GET /api/v1/founder/overview returning 404 for anyone
// not on the allowlist). The distinct dark banner is intentional: anyone
// who lands here (a screenshot, a screen share) should immediately see
// this isn't the product a business owner uses.
export default function OpsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-muted/30">
      <div className="flex items-center gap-2 bg-foreground px-4 py-2 text-background sm:px-8">
        <ShieldAlert className="size-4" />
        <span className="text-sm font-medium">Founder Operations — Internal Only</span>
      </div>
      <div className="mx-auto max-w-6xl p-4 sm:p-8">{children}</div>
    </div>
  );
}
