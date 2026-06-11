import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { QueueStats, SubmissionRow } from "@/lib/api";
import { QueuePage } from "./QueuePage";

const submissions = vi.fn();
const queueStats = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      submissions: () => submissions(),
      queueStats: () => queueStats(),
    },
  };
});

function row(p: Partial<SubmissionRow> & Pick<SubmissionRow, "id">): SubmissionRow {
  return {
    created_at: "2026-06-11T12:00:00Z",
    status: "completed",
    brand_name: "Brand",
    applicant: "Applicant",
    class_type: "Class",
    overall: "pass",
    warning_verdict: "compliant",
    processing_ms: 3000,
    image_filename: "x.png",
    decision: null,
    decided_at: null,
    ...p,
  };
}

const ROWS: SubmissionRow[] = [
  row({ id: 1, brand_name: "Old Tom", overall: "pass", decision: "approve" }),
  row({ id: 2, brand_name: "Cedar Ridge", overall: "fail" }), // needs review
  row({ id: 3, brand_name: "Hopworks", overall: "pass" }), // pending
];

const STATS: QueueStats = { pending: 1, flagged: 1, cleared_week: 1, avg_scan_ms: 3000 };

function rowOrder(): string[] {
  // Each data row is a role=button with an aria-label naming the brand.
  return screen
    .getAllByRole("button", { name: /Open submission/i })
    .map((el) => el.getAttribute("aria-label") ?? "");
}

beforeEach(() => {
  submissions.mockResolvedValue(ROWS);
  queueStats.mockResolvedValue(STATS);
});
afterEach(() => vi.restoreAllMocks());

async function renderQueue() {
  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );
  await screen.findByLabelText(/Open submission 1/i);
}

describe("QueuePage sorting & filtering", () => {
  it("defaults to newest-first (id descending)", async () => {
    await renderQueue();
    const ids = rowOrder().map((l) => l.match(/submission (\d)/)?.[1]);
    expect(ids).toEqual(["3", "2", "1"]);
  });

  it("sorts by brand ascending when the Brand header is clicked", async () => {
    await renderQueue();
    fireEvent.click(screen.getByRole("button", { name: /Sort by Brand/i }));
    const brands = rowOrder().map((l) => l.replace(/Open submission \d, /, "").split(",")[0]);
    expect(brands).toEqual(["Cedar Ridge", "Hopworks", "Old Tom"]);
  });

  it("toggles sort direction on a second click of the same header", async () => {
    await renderQueue();
    // Re-query between clicks: the header's aria-label changes (and the node
    // re-renders) once a column becomes the active sort.
    fireEvent.click(screen.getByRole("button", { name: /Sort by Brand/i })); // asc
    fireEvent.click(screen.getByRole("button", { name: /Sort by Brand.*ascending/i })); // desc
    const brands = rowOrder().map((l) => l.replace(/Open submission \d, /, "").split(",")[0]);
    expect(brands).toEqual(["Old Tom", "Hopworks", "Cedar Ridge"]);
  });

  it("filters by a text query over brand", async () => {
    await renderQueue();
    fireEvent.change(screen.getByLabelText(/Search the queue/i), {
      target: { value: "cedar" },
    });
    await waitFor(() => expect(rowOrder()).toHaveLength(1));
    expect(rowOrder()[0]).toMatch(/Cedar Ridge/);
  });

  it("filters by status", async () => {
    await renderQueue();
    fireEvent.change(screen.getByLabelText(/Filter by status/i), {
      target: { value: "approved" },
    });
    await waitFor(() => expect(rowOrder()).toHaveLength(1));
    expect(rowOrder()[0]).toMatch(/Old Tom/);
  });

  it("shows an empty-filter message and clears filters", async () => {
    await renderQueue();
    fireEvent.change(screen.getByLabelText(/Search the queue/i), {
      target: { value: "zzz no match" },
    });
    expect(await screen.findByText(/No submissions match your filters/i)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: /Clear filters/i }));
    await waitFor(() => expect(rowOrder()).toHaveLength(3));
  });

  it("keeps the count summary in sync", async () => {
    await renderQueue();
    const bar = screen.getByText(/3 submissions/i);
    expect(within(document.body).getByText(/3 submissions/i)).toBe(bar);
    fireEvent.change(screen.getByLabelText(/Filter by status/i), {
      target: { value: "approved" },
    });
    expect(await screen.findByText(/1 of 3 submissions/i)).toBeDefined();
  });
});
