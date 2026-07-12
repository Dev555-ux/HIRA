"use client";

import { AlertTriangle } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title="Something went wrong"
      description={error.message}
      action={
        <Button size="sm" variant="outline" onClick={reset}>
          Try again
        </Button>
      }
    />
  );
}
