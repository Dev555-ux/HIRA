import { SignIn } from "@clerk/nextjs";
import { AuthPageShell } from "@/components/auth/auth-page-shell";
import { authEnabled } from "@/lib/config";

export default function SignInPage() {
  if (!authEnabled) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-center">
        <p className="max-w-md text-sm text-muted-foreground">
          Clerk isn&apos;t configured in this environment — sign-in isn&apos;t
          available in mock/dev mode.
        </p>
      </div>
    );
  }

  return (
    <AuthPageShell
      heading="Welcome back"
      subheading="Sign in to your HIRA dashboard."
    >
      <SignIn />
    </AuthPageShell>
  );
}
