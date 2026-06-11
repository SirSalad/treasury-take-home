import type { AuditEvent } from "@/lib/api";

/**
 * Presentation helpers for audit events — the action vocabulary mapped to
 * human labels, an accent color, and a one-line summary drawn from the event
 * detail. Kept out of the components so the page and the per-submission
 * timeline render events identically.
 */

export interface AuditDisplay {
  label: string;
  color: string;
  bg: string;
  summary: string;
}

const DECISION_LABEL: Record<string, string> = {
  approve: "Approved",
  request_changes: "Changes requested",
  request_info: "More info requested",
};

function str(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

export function describeAuditEvent(event: AuditEvent): AuditDisplay {
  const detail = event.detail ?? {};

  if (event.action === "decision.recorded") {
    const decision = str(detail.decision);
    const note = str(detail.note);
    return {
      label: "Decision recorded",
      color: "#1a4480",
      bg: "#e1effa",
      summary: [decision ? (DECISION_LABEL[decision] ?? decision) : null, note]
        .filter(Boolean)
        .join(" — "),
    };
  }

  if (event.action === "verification.completed") {
    const overall = str(detail.overall);
    const brand = str(detail.brand_name);
    const ms = typeof detail.processing_ms === "number" ? detail.processing_ms : null;
    const overallColor =
      overall === "pass" ? "#226e2a" : overall === "fail" ? "#b50909" : "#7a5a00";
    return {
      label: "Verification completed",
      color: overallColor,
      bg: "#f4f5f6",
      summary: [
        brand,
        overall ? `verdict: ${overall}` : null,
        ms != null ? `${(ms / 1000).toFixed(1)}s` : null,
      ]
        .filter(Boolean)
        .join(" · "),
    };
  }

  if (event.action === "verification.failed") {
    return {
      label: "Verification failed",
      color: "#b50909",
      bg: "#fdeced",
      summary: str(detail.error) ?? str(detail.image_filename) ?? "Unreadable image",
    };
  }

  // Unknown action: render it rather than hiding it (the log is append-only).
  return { label: event.action, color: "#3d4551", bg: "#f4f5f6", summary: "" };
}

export function formatAuditTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
