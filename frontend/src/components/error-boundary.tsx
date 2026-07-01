"use client";

import { AlertTriangle } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";

interface State {
  hasError: boolean;
  message?: string;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  reset = () => this.setState({ hasError: false, message: undefined });

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
          <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/15">
            <AlertTriangle className="size-6 text-destructive" />
          </div>
          <h3 className="text-sm font-semibold">Something went wrong</h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            {this.state.message ?? "An unexpected error occurred."}
          </p>
          <Button className="mt-4" size="sm" variant="outline" onClick={this.reset}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
