"use client";

import { AlertTriangle } from "lucide-react";
import * as React from "react";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

interface State {
  hasError: boolean;
  message?: string;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; resetKey?: string },
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

  componentDidUpdate(prevProps: Readonly<{ children: React.ReactNode; resetKey?: string }>) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.reset();
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <EmptyState
          icon={AlertTriangle}
          title="Something went wrong"
          description={this.state.message ?? "An unexpected error occurred."}
          action={
            <Button size="sm" variant="outline" onClick={this.reset}>
              Try again
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
