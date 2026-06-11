import { describe, expect, it } from "vitest";

import type { AuditEvent } from "@/lib/api";
import { describeAuditEvent, formatAuditTime } from "@/lib/audit";

function event(partial: Partial<AuditEvent>): AuditEvent {
  return {
    id: 1,
    created_at: "2026-06-11T12:00:00Z",
    action: "verification.completed",
    actor: "reviewer",
    submission_id: 7,
    detail: null,
    ...partial,
  };
}

describe("describeAuditEvent", () => {
  it("summarizes a completed verification with brand, verdict, and timing", () => {
    const view = describeAuditEvent(
      event({ detail: { brand_name: "Old Tom", overall: "pass", processing_ms: 3100 } }),
    );
    expect(view.label).toBe("Verification completed");
    expect(view.summary).toBe("Old Tom · verdict: pass · 3.1s");
    expect(view.color).toBe("#226e2a"); // green for pass
  });

  it("maps the decision action to a human label and note", () => {
    const view = describeAuditEvent(
      event({
        action: "decision.recorded",
        detail: { decision: "request_changes", note: "Fix ABV" },
      }),
    );
    expect(view.label).toBe("Decision recorded");
    expect(view.summary).toBe("Changes requested — Fix ABV");
  });

  it("renders an unknown action verbatim rather than hiding it", () => {
    const view = describeAuditEvent(event({ action: "something.new", detail: null }));
    expect(view.label).toBe("something.new");
    expect(view.summary).toBe("");
  });
});

describe("formatAuditTime", () => {
  it("renders a dash for a null timestamp", () => {
    expect(formatAuditTime(null)).toBe("—");
  });

  it("formats an ISO timestamp", () => {
    expect(formatAuditTime("2026-06-11T12:00:00Z")).toMatch(/Jun 11/);
  });
});
