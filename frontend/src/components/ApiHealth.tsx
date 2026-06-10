import { useEffect, useState } from "react";

import { api, type HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

/**
 * Small backend connectivity indicator. Confirms the typed API client and the
 * dev proxy are wired up end to end; verification endpoints layer on later.
 */
export function ApiHealth() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    api
      .health(controller.signal)
      .then((data) => setState({ kind: "ok", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => controller.abort();
  }, []);

  const dot =
    state.kind === "ok"
      ? "bg-match"
      : state.kind === "error"
        ? "bg-mismatch"
        : "bg-warning animate-pulse";

  return (
    <section
      className="flex items-center gap-2 rounded-md border bg-secondary px-3 py-2 text-sm text-muted-foreground"
      aria-live="polite"
    >
      <span className={cn("inline-block size-2.5 rounded-full", dot)} aria-hidden="true" />
      {state.kind === "loading" && <span>Checking backend connection…</span>}
      {state.kind === "ok" && <span>Backend connected — API v{state.data.version}</span>}
      {state.kind === "error" && (
        <span>Backend unavailable (start the API, or this is expected offline).</span>
      )}
    </section>
  );
}
