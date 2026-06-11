import { AlertTriangle } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * App-wide safety net for unexpected render errors. Without it, a thrown error
 * anywhere in the tree blanks the whole page; instead we show a calm, readable
 * recovery screen with a reload action — the "73-year-old usability" bar means
 * a dead-end white screen is never acceptable. Announced via `role="alert"` so
 * assistive tech surfaces it immediately.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Surface to the console for diagnostics; a real deployment would forward
    // this to an error-reporting service.
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-dvh items-center justify-center bg-background p-6">
          <div
            role="alert"
            className="max-w-md space-y-4 rounded-lg border-2 border-destructive bg-mismatch-muted p-6 text-center"
          >
            <AlertTriangle className="mx-auto size-10 text-destructive" aria-hidden="true" />
            <div className="space-y-1">
              <h1 className="text-xl font-bold text-foreground">The page hit an error</h1>
              <p className="text-sm text-muted-foreground">
                The page could not continue. Reload to try again; if the error repeats, contact your
                administrator.
              </p>
            </div>
            <Button onClick={() => window.location.reload()}>Reload the page</Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
