import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError, type AuditEvent } from "@/lib/api";
import { describeAuditEvent, formatAuditTime } from "@/lib/audit";

/**
 * Audit Log — the append-only record of every consequential action
 * (verification run, reviewer decision). The submissions table holds current
 * state; this is the history an auditor or FOIA request actually asks for.
 * Read-only by design: the API only ever appends.
 */

const GRID = "grid grid-cols-[150px_180px_1fr_92px] items-center gap-0";

export function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .audit(undefined, controller.signal)
      .then(setEvents)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not load the audit log.");
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="pb-10">
      <div className="mb-[18px]">
        <h2 className="mb-[5px] text-[30px] font-extrabold tracking-[-.6px] text-fed-navy">
          Audit Log
        </h2>
        <p className="text-sm text-fed-gray">
          Every verification and reviewer decision, recorded in an append-only trail. Read-only —
          entries are never edited or deleted.
        </p>
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
          <div>When</div>
          <div>Event</div>
          <div>Details</div>
          <div>Submission</div>
        </div>
        {events === null && !error && (
          <p className="px-[18px] py-6 text-sm text-fed-gray">Loading the audit log…</p>
        )}
        {events?.length === 0 && (
          <p className="px-[18px] py-10 text-center text-[13.5px] text-fed-gray">
            No activity recorded yet.
          </p>
        )}
        {events?.map((event) => {
          const view = describeAuditEvent(event);
          return (
            <div
              key={event.id}
              className={`${GRID} border-b border-fed-line-soft px-[18px] py-3 last:border-b-0`}
            >
              <div className="text-[12.5px] tabular-nums text-fed-gray">
                {formatAuditTime(event.created_at)}
              </div>
              <div>
                <span
                  className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold"
                  style={{ color: view.color, background: view.bg }}
                >
                  {view.label}
                </span>
              </div>
              <div className="truncate pr-3 text-[13px] text-fed-slate" title={view.summary}>
                {view.summary || <span className="text-fed-gray-light">—</span>}
              </div>
              <div className="text-[13px] tabular-nums">
                {event.submission_id != null ? (
                  <Link
                    to={`/review/${event.submission_id}`}
                    className="font-semibold text-fed-blue hover:underline"
                  >
                    SUB-{String(event.submission_id).padStart(4, "0")}
                  </Link>
                ) : (
                  <span className="text-fed-gray-light">—</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
