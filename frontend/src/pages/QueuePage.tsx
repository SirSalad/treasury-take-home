import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError, type QueueStats, type SubmissionRow } from "@/lib/api";

/**
 * My Review Queue — the workspace home (claude-design).
 *
 * Four stat cards over a sortable, filterable table of submissions. Row status
 * is the human-workflow state derived from the automated verdict plus any
 * recorded reviewer decision, not the raw pipeline status. Sorting and
 * filtering are client-side over the loaded set.
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

type SortCol = "status" | "id" | "brand" | "applicant" | "class" | "submitted";
type SortDir = "asc" | "desc";

function compare(a: SubmissionRow, b: SubmissionRow, col: SortCol): number {
  switch (col) {
    case "id":
      return a.id - b.id;
    case "status":
      return STATUS_DEF[statusKey(a)].order - STATUS_DEF[statusKey(b)].order;
    case "brand":
      return (a.brand_name ?? "").localeCompare(b.brand_name ?? "");
    case "applicant":
      return (a.applicant ?? "").localeCompare(b.applicant ?? "");
    case "class":
      return (a.class_type ?? "").localeCompare(b.class_type ?? "");
    case "submitted":
      // created_at is ISO-8601, so lexical order is chronological order.
      return (a.created_at ?? "").localeCompare(b.created_at ?? "");
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
}

const GRID = "grid grid-cols-[168px_110px_1.4fr_1.3fr_1fr_118px_44px] items-center gap-0";

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

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusKey | "all">("all");
  const [sortCol, setSortCol] = useState<SortCol>("id");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

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

  const visible = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    const filtered = rows.filter((row) => {
      if (statusFilter !== "all" && statusKey(row) !== statusFilter) return false;
      if (q) {
        const hay = [
          row.brand_name,
          row.applicant,
          row.class_type,
          `sub-${String(row.id).padStart(4, "0")}`,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => compare(a, b, sortCol) * dir);
  }, [rows, query, statusFilter, sortCol, sortDir]);

  function toggleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      // Sensible default direction per column: newest/most-urgent first.
      setSortDir(col === "id" || col === "submitted" ? "desc" : "asc");
    }
  }

  const open = (id: number) => navigate(`/review/${id}`);
  const filtering = query.trim() !== "" || statusFilter !== "all";

  function SortHeader({ col, label }: { col: SortCol; label: string }) {
    const active = sortCol === col;
    return (
      <button
        type="button"
        onClick={() => toggleSort(col)}
        aria-label={`Sort by ${label}${active ? (sortDir === "asc" ? ", ascending" : ", descending") : ""}`}
        className="flex items-center gap-1 text-left uppercase tracking-[.5px] hover:text-fed-blue"
      >
        {label}
        <span aria-hidden="true" className={active ? "text-fed-blue" : "text-[#c4c8cc]"}>
          {active ? (sortDir === "asc" ? "▲" : "▼") : "▾"}
        </span>
      </button>
    );
  }

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
          label="Pending in your queue"
          accent="#005ea2"
        />
        <StatCard
          value={stats ? String(stats.flagged) : "–"}
          label="Flagged for your judgment"
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
          value={stats?.avg_scan_ms != null ? `${(stats.avg_scan_ms / 1000).toFixed(1)}s` : "–"}
          label="Avg. scan time"
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

      {/* Filter bar */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="grow sm:grow-0">
          <label htmlFor="queue-search" className="sr-only">
            Search the queue by brand, applicant, class, or ID
          </label>
          <input
            id="queue-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search brand, applicant, class, ID…"
            className="w-full rounded-md border border-[#c4c8cc] px-3 py-2 text-sm text-fed-ink focus:border-fed-blue focus:outline-none sm:w-[320px]"
          />
        </div>
        <div>
          <label htmlFor="queue-status" className="sr-only">
            Filter by status
          </label>
          <select
            id="queue-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusKey | "all")}
            className="rounded-md border border-[#c4c8cc] bg-white px-3 py-2 text-sm font-semibold text-fed-ink focus:border-fed-blue focus:outline-none"
          >
            <option value="all">All statuses</option>
            {(Object.keys(STATUS_DEF) as StatusKey[]).map((key) => (
              <option key={key} value={key}>
                {STATUS_DEF[key].label}
              </option>
            ))}
          </select>
        </div>
        {filtering && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setStatusFilter("all");
            }}
            className="text-sm font-semibold text-fed-blue hover:underline"
          >
            Clear filters
          </button>
        )}
        {rows && (
          <span className="ml-auto text-[13px] text-fed-gray" aria-live="polite">
            {filtering ? `${visible.length} of ${rows.length}` : `${rows.length}`}{" "}
            {rows.length === 1 ? "submission" : "submissions"}
          </span>
        )}
      </div>

      <div className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
        <div
          className={`${GRID} border-b-2 border-[#d6d7d9] bg-fed-head-bg px-[18px] py-3 text-[11.5px] font-bold text-fed-gray`}
        >
          <SortHeader col="status" label="Status" />
          <SortHeader col="id" label="ID" />
          <SortHeader col="brand" label="Brand" />
          <SortHeader col="applicant" label="Applicant" />
          <SortHeader col="class" label="Class / Type" />
          <SortHeader col="submitted" label="Submitted" />
          <div />
        </div>
        {rows === null && !error && (
          <p className="px-[18px] py-6 text-sm text-fed-gray">Loading the queue…</p>
        )}
        {rows?.length === 0 && (
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
        )}
        {rows && rows.length > 0 && visible.length === 0 && (
          <p className="px-[18px] py-10 text-center text-[13.5px] text-fed-gray">
            No submissions match your filters.
          </p>
        )}
        {visible.map((row) => {
          const status = STATUS_DEF[statusKey(row)];
          return (
            <div
              key={row.id}
              role="button"
              tabIndex={0}
              aria-label={`Open submission ${row.id}, ${row.brand_name ?? "unknown brand"}, ${status.label}`}
              onClick={() => open(row.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  open(row.id);
                }
              }}
              className={`${GRID} cursor-pointer border-b border-fed-line-soft px-[18px] py-3.5 transition-colors last:border-b-0 hover:bg-fed-blue-wash hover:shadow-[inset_3px_0_0_#005ea2] focus-visible:bg-fed-blue-wash focus-visible:shadow-[inset_3px_0_0_#005ea2] focus-visible:outline-none`}
            >
              <div>
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
              </div>
              <div className="text-[13.5px] font-semibold tabular-nums text-fed-blue">
                SUB-{String(row.id).padStart(4, "0")}
              </div>
              <div className="truncate pr-2 text-sm font-bold text-fed-ink">
                {row.brand_name ?? "—"}
              </div>
              <div className="truncate pr-2 text-[13.5px] text-fed-slate">
                {row.applicant ?? "—"}
              </div>
              <div className="truncate pr-2 text-[13px] text-fed-gray">{row.class_type ?? "—"}</div>
              <div className="text-[13px] font-semibold tabular-nums text-fed-gray">
                {formatDate(row.created_at)}
              </div>
              <div aria-hidden="true" className="text-right text-[17px] text-fed-gray-light">
                ›
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
