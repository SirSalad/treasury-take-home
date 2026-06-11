import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError, type QueueStats, type SubmissionRow } from "@/lib/api";

/**
 * My Review Queue — the workspace home (claude-design).
 *
 * Four stat cards over a clickable table of recent submissions. Row status is
 * the human-workflow state derived from the automated verdict plus any
 * recorded reviewer decision, not the raw pipeline status.
 */

interface QueueStatus {
  label: string;
  color: string;
  bg: string;
}

function rowStatus(row: SubmissionRow): QueueStatus {
  if (row.status === "failed") {
    return { label: "Unreadable", color: "#b50909", bg: "#fdeced" };
  }
  switch (row.decision) {
    case "approve":
      return { label: "Approved", color: "#226e2a", bg: "#eaf4ec" };
    case "request_changes":
      return { label: "Changes Requested", color: "#b50909", bg: "#fdeced" };
    case "request_info":
      return { label: "Info Requested", color: "#3d4551", bg: "#eef0f2" };
    default:
      break;
  }
  if (row.overall === "warning" || row.overall === "fail") {
    return { label: "Needs Review", color: "#7a5a00", bg: "#faf3d1" };
  }
  return { label: "Pending Review", color: "#005ea2", bg: "#e1effa" };
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
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

  const open = (id: number) => navigate(`/review/${id}`);

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

      <div className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
        <div
          className={`${GRID} border-b-2 border-[#d6d7d9] bg-fed-head-bg px-[18px] py-3 text-[11.5px] font-bold uppercase tracking-[.5px] text-fed-gray`}
        >
          <div>Status</div>
          <div>ID</div>
          <div>Brand</div>
          <div>Applicant</div>
          <div>Class / Type</div>
          <div>Submitted</div>
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
        {rows?.map((row) => {
          const status = rowStatus(row);
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
              className={`${GRID} cursor-pointer border-b border-fed-line-soft px-[18px] py-3.5 transition-colors last:border-b-0 hover:bg-fed-blue-wash hover:shadow-[inset_3px_0_0_#005ea2] focus-visible:bg-fed-blue-wash focus-visible:outline-none focus-visible:shadow-[inset_3px_0_0_#005ea2]`}
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
