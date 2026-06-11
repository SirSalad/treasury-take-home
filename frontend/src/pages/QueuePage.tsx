import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { api, ApiError, type QueueStats, type SubmissionRow } from "@/lib/api";

/**
 * My Review Queue — the workspace home (claude-design).
 *
 * Four stat cards over a sortable, filterable table of submissions (the shared
 * {@link DataTable}). Row status is the human-workflow state derived from the
 * automated verdict plus any recorded reviewer decision, not the raw pipeline
 * status.
 */

type StatusKey = "needs_review" | "pending" | "changes" | "info" | "unreadable" | "approved";

// Order doubles as the status-column sort rank: most-urgent first.
const STATUS_DEF: Record<StatusKey, { label: string; color: string; bg: string; order: number }> = {
  needs_review: { label: "Needs Review", color: "#7a5a00", bg: "#faf3d1", order: 0 },
  pending: { label: "Pending Review", color: "#005ea2", bg: "#e1effa", order: 1 },
  changes: { label: "Changes Requested", color: "#b50909", bg: "#fdeced", order: 2 },
  info: { label: "Info Requested", color: "#3d4551", bg: "#eef0f2", order: 3 },
  unreadable: { label: "Unreadable", color: "#b50909", bg: "#fdeced", order: 4 },
  approved: { label: "Approved", color: "#226e2a", bg: "#eaf4ec", order: 5 },
};

function statusKey(row: SubmissionRow): StatusKey {
  if (row.status === "failed") return "unreadable";
  if (row.decision === "approve") return "approved";
  if (row.decision === "request_changes") return "changes";
  if (row.decision === "request_info") return "info";
  if (row.overall === "warning" || row.overall === "fail") return "needs_review";
  return "pending";
}

function subId(id: number): string {
  return `SUB-${String(id).padStart(4, "0")}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
}

const COLUMNS: DataTableColumn<SubmissionRow>[] = [
  {
    key: "status",
    header: "Status",
    width: "168px",
    sortValue: (row) => STATUS_DEF[statusKey(row)].order,
    cell: (row) => {
      const status = STATUS_DEF[statusKey(row)];
      return (
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold"
          style={{ color: status.color, background: status.bg }}
        >
          <span
            aria-hidden="true"
            className="h-[7px] w-[7px] rounded-full"
            style={{ background: status.color }}
          />
          {status.label}
        </span>
      );
    },
  },
  {
    key: "id",
    header: "ID",
    width: "110px",
    sortValue: (row) => row.id,
    defaultDir: "desc",
    cell: (row) => (
      <span className="text-[13.5px] font-semibold tabular-nums text-fed-blue">
        {subId(row.id)}
      </span>
    ),
  },
  {
    key: "brand",
    header: "Brand",
    width: "1.4fr",
    sortValue: (row) => row.brand_name ?? "",
    cell: (row) => (
      <span className="block truncate pr-2 text-sm font-bold text-fed-ink">
        {row.brand_name ?? "—"}
      </span>
    ),
  },
  {
    key: "applicant",
    header: "Applicant",
    width: "1.3fr",
    sortValue: (row) => row.applicant ?? "",
    cell: (row) => (
      <span className="block truncate pr-2 text-[13.5px] text-fed-slate">
        {row.applicant ?? "—"}
      </span>
    ),
  },
  {
    key: "class",
    header: "Class / Type",
    width: "1fr",
    sortValue: (row) => row.class_type ?? "",
    cell: (row) => (
      <span className="block truncate pr-2 text-[13px] text-fed-gray">{row.class_type ?? "—"}</span>
    ),
  },
  {
    key: "submitted",
    header: "Submitted",
    width: "118px",
    sortValue: (row) => row.created_at ?? "",
    defaultDir: "desc",
    cell: (row) => (
      <span className="text-[13px] font-semibold tabular-nums text-fed-gray">
        {formatDate(row.created_at)}
      </span>
    ),
  },
  {
    key: "chevron",
    header: "",
    width: "44px",
    cell: () => (
      <span aria-hidden="true" className="block text-right text-[17px] text-fed-gray-light">
        ›
      </span>
    ),
  },
];

function StatCard({
  value,
  label,
  accent,
  valueColor,
}: {
  value: string;
  label: string;
  accent: string;
  valueColor?: string;
}) {
  return (
    <div
      className="rounded-[10px] border border-fed-line bg-white px-5 py-[18px] shadow-card"
      style={{ borderLeft: `4px solid ${accent}` }}
    >
      <div
        className="text-[30px] font-extrabold leading-none text-fed-navy"
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </div>
      <div className="mt-[5px] text-[13px] font-semibold text-fed-gray">{label}</div>
    </div>
  );
}

export function QueuePage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<SubmissionRow[] | null>(null);
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.submissions(controller.signal), api.queueStats(controller.signal)])
      .then(([submissions, queueStats]) => {
        setRows(submissions);
        setStats(queueStats);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not load the queue.");
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="pb-10">
      <div className="mb-[18px] flex flex-wrap items-end justify-between gap-3.5">
        <div>
          <h2 className="mb-[5px] text-[30px] font-extrabold tracking-[-.6px] text-fed-navy">
            My Review Queue
          </h2>
          <p className="text-sm text-fed-gray">
            Pick up where you left off, or start a new verification.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            to="/batch"
            className="flex items-center gap-2 rounded-md border-2 border-fed-blue bg-white px-[18px] py-[9px] text-[14.5px] font-bold text-fed-blue hover:bg-fed-blue-wash"
          >
            <span aria-hidden="true" className="text-base">
              ☰
            </span>
            Batch Upload
          </Link>
          <Link
            to="/verify"
            className="flex items-center gap-2 rounded-md border-2 border-fed-blue bg-fed-blue px-5 py-[9px] text-[14.5px] font-bold text-white shadow-[0_1px_0_rgba(0,0,0,.12)] hover:bg-[#0b4778]"
          >
            <span aria-hidden="true" className="text-[17px] leading-none">
              +
            </span>
            New Verification
          </Link>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <StatCard
          value={stats ? String(stats.pending) : "–"}
          label="Pending review"
          accent="#005ea2"
        />
        <StatCard
          value={stats ? String(stats.flagged) : "–"}
          label="Flagged for review"
          accent="#7a5a00"
          valueColor="#7a5a00"
        />
        <StatCard
          value={stats ? String(stats.cleared_week) : "–"}
          label="Cleared this week"
          accent="#226e2a"
          valueColor="#226e2a"
        />
        <StatCard
          value={
            stats?.median_scan_ms != null ? `${(stats.median_scan_ms / 1000).toFixed(1)}s` : "–"
          }
          label="Median scan time"
          accent="#5b616b"
        />
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-[#f3c9cb] bg-[#fef6f6] px-4 py-3 text-sm text-fed-red-deep"
        >
          {error}
        </div>
      )}

      <DataTable
        columns={COLUMNS}
        rows={rows}
        pageSize={25}
        getRowKey={(row) => row.id}
        onRowClick={(row) => navigate(`/review/${row.id}`)}
        rowAriaLabel={(row) =>
          `Open submission ${row.id}, ${row.brand_name ?? "unknown brand"}, ${STATUS_DEF[statusKey(row)].label}`
        }
        search={{
          ariaLabel: "Search the queue by brand, applicant, class, or ID",
          placeholder: "Search brand, applicant, class, ID…",
          text: (row) =>
            [row.brand_name, row.applicant, row.class_type, subId(row.id)]
              .filter(Boolean)
              .join(" "),
        }}
        filters={[
          {
            key: "status",
            label: "Filter by status",
            options: [
              { value: "all", label: "All statuses" },
              ...(Object.keys(STATUS_DEF) as StatusKey[]).map((key) => ({
                value: key,
                label: STATUS_DEF[key].label,
              })),
            ],
            predicate: (row, value) => statusKey(row) === value,
          },
        ]}
        defaultSort={{ key: "id", dir: "desc" }}
        countNoun={["submission", "submissions"]}
        loadingMessage="Loading the queue…"
        noMatchMessage="No submissions match your filters."
        emptyState={
          <div className="px-[18px] py-10 text-center">
            <p className="mb-1 text-[15px] font-bold text-fed-ink">Nothing in the queue yet</p>
            <p className="text-[13.5px] text-fed-gray">
              Run a{" "}
              <Link className="font-semibold text-fed-blue underline" to="/verify">
                new verification
              </Link>{" "}
              and it will appear here for review.
            </p>
          </div>
        }
      />
    </div>
  );
}
