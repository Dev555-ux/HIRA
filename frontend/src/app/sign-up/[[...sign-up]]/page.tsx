import { SignUp } from "@clerk/nextjs";
import { authEnabled } from "@/lib/config";

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
    <div className="flex min-h-screen items-center justify-center p-4">
      <SignUp />
    </div>
  );
}
