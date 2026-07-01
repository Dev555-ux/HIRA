"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/15">
        <AlertTriangle className="size-6 text-destructive" />
      </div>
      <h3 className="text-sm font-semibold">Something went wrong</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{error.message}</p>
      <Button className="mt-4" size="sm" variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
