import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { App } from "./App";
import type { QueueStats, SubmissionDetail, SubmissionRow } from "./lib/api";
import { SAMPLE_RESULT } from "./lib/verification.fixture";
import { AuditPage } from "./pages/AuditPage";
import { BatchPage } from "./pages/BatchPage";
import { QueuePage } from "./pages/QueuePage";
import { ReviewPage } from "./pages/ReviewPage";
import { VerifyPage } from "./pages/VerifyPage";

const ROW: SubmissionRow = {
  id: 7,
  created_at: "2026-06-11T12:00:00Z",
  status: "completed",
  brand_name: "Stone's Throw IPA",
  applicant: "Stone's Throw Brewing Co.",
  class_type: "Malt Beverage",
  overall: "warning",
  warning_verdict: "compliant",
  processing_ms: 3100,
  image_filename: "stones_throw.png",
  decision: null,
  decided_at: null,
};

const DETAIL: SubmissionDetail = {
  ...ROW,
  result: SAMPLE_RESULT,
  error: null,
  decision_note: null,
  application: { brand_name: "Stone's Throw IPA", product_type: "malt_beverage" },
};

const STATS: QueueStats = { pending: 3, flagged: 1, cleared_week: 12, avg_scan_ms: 3100 };

// The queue and review pages fetch on mount; serve them canned data so the
// audit exercises the fully-rendered states, not the loading placeholders.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      submissions: () => Promise.resolve([ROW]),
      queueStats: () => Promise.resolve(STATS),
      submission: () => Promise.resolve(DETAIL),
      submissionImageUrl: () => "/sample-label.png",
      audit: () =>
        Promise.resolve([
          {
            id: 2,
            created_at: "2026-06-11T12:05:00Z",
            action: "decision.recorded",
            actor: "reviewer",
            submission_id: 7,
            detail: { decision: "approve", note: "Looks good" },
          },
          {
            id: 1,
            created_at: "2026-06-11T12:00:00Z",
            action: "verification.completed",
            actor: "reviewer",
            submission_id: 7,
            detail: { brand_name: "Stone's Throw IPA", overall: "warning", processing_ms: 3100 },
          },
        ]),
    },
  };
});

// Gate on WCAG 2.0 + 2.1, levels A and AA — the standard for federal sites.
const AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoAaViolations(ui: ReactElement, ready?: () => Promise<unknown>) {
  const { container } = render(ui);
  if (ready) await ready();
  const results = await axe(container, { runOnly: { type: "tag", values: AA_TAGS } });
  expect(results).toHaveNoViolations();
}

afterEach(cleanup);

describe("WCAG 2.1 AA accessibility", () => {
  it("app shell / review queue", async () => {
    await expectNoAaViolations(<App />, () => screen.findByText(/Stone's Throw Brewing Co./i));
  });

  it("review queue (stat cards + table)", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <QueuePage />
      </MemoryRouter>,
      () => screen.findByText(/Pending in your queue/i),
    );
  });

  it("review screen (checklist, warning hero, decision panel)", async () => {
    await expectNoAaViolations(
      <MemoryRouter initialEntries={["/review/7"]}>
        <Routes>
          <Route path="/review/:id" element={<ReviewPage />} />
        </Routes>
      </MemoryRouter>,
      () => screen.findByText(/Verification Checklist/i),
    );
  });

  it("audit log", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
      () => screen.findByText(/Decision recorded/i),
    );
  });

  it("verify form (empty state)", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <VerifyPage />
      </MemoryRouter>,
    );
  });

  it("batch upload page", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <BatchPage />
      </MemoryRouter>,
    );
  });
});
