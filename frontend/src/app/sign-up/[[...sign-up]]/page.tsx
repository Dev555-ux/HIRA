import { SignUp } from "@clerk/nextjs";
import type { Metadata } from "next";
import { AuthPageShell } from "@/components/auth/auth-page-shell";
import { authEnabled } from "@/lib/config";
import { pageMetadata } from "@/lib/seo";

// Clerk's multi-step flow lives under this catch-all (e.g. /sign-up/factor-one);
// every step canonicalises to the entry URL.
export const metadata: Metadata = pageMetadata({
  title: "Get started",
  description: "Create your HIRA account and set up an AI employee that answers your customers on WhatsApp — takes about two minutes.",
  path: "/sign-up",
});

export default function SignUpPage() {
  if (!authEnabled) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-center">
        <p className="max-w-md text-sm text-muted-foreground">
          Clerk isn&apos;t configured in this environment — sign-up isn&apos;t
          available in mock/dev mode.
        </p>
      </div>
    );
  }

  return (
    <AuthPageShell
      heading="Hire your first AI employee"
      subheading="Create your HIRA account — takes about two minutes."
    >
      <SignUp />
    </AuthPageShell>
  );
}
