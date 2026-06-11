import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { api, ApiError, type AuditEvent } from "@/lib/api";
import { describeAuditEvent, formatAuditTime } from "@/lib/audit";

/**
 * Audit Log — the append-only record of every consequential action
 * (verification run, reviewer decision). The submissions table holds current
 * state; this is the history an auditor or FOIA request actually asks for.
 * Read-only by design: the API only ever appends. Built from the shared
 * {@link DataTable}, so it sorts, searches, and filters like the queue.
 */

function subId(id: number): string {
  return `SUB-${String(id).padStart(4, "0")}`;
}

const COLUMNS: DataTableColumn<AuditEvent>[] = [
  {
    key: "when",
    header: "When",
    width: "180px",
    sortValue: (event) => event.created_at ?? "",
    defaultDir: "desc",
    cell: (event) => (
      <span className="text-[12.5px] tabular-nums text-fed-gray">
        {formatAuditTime(event.created_at)}
      </span>
    ),
  },
  {
    key: "event",
    header: "Event",
    width: "190px",
    sortValue: (event) => describeAuditEvent(event).label,
    cell: (event) => {
      const view = describeAuditEvent(event);
      return (
        <span
          className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold"
          style={{ color: view.color, background: view.bg }}
        >
          {view.label}
        </span>
      );
    },
  },
  {
    key: "details",
    header: "Details",
    width: "1fr",
    cell: (event) => {
      const view = describeAuditEvent(event);
      return (
        <span className="block truncate pr-3 text-[13px] text-fed-slate" title={view.summary}>
          {view.summary || <span className="text-fed-gray-light">—</span>}
        </span>
      );
    },
  },
  {
    key: "submission",
    header: "Submission",
    width: "120px",
    sortValue: (event) => event.submission_id ?? -1,
    cell: (event) =>
      event.submission_id != null ? (
        <Link
          to={`/review/${event.submission_id}`}
          className="text-[13px] font-semibold tabular-nums text-fed-blue hover:underline"
        >
          {subId(event.submission_id)}
        </Link>
      ) : (
        <span className="text-[13px] text-fed-gray-light">—</span>
      ),
  },
];

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

      <DataTable
        columns={COLUMNS}
        rows={events}
        pageSize={50}
        getRowKey={(event) => event.id}
        search={{
          ariaLabel: "Search the audit log by event, details, or submission",
          placeholder: "Search events, details, ID…",
          text: (event) => {
            const view = describeAuditEvent(event);
            const sub = event.submission_id != null ? subId(event.submission_id) : "";
            return `${view.label} ${view.summary} ${sub}`;
          },
        }}
        filters={[
          {
            key: "action",
            label: "Filter by event type",
            options: [
              { value: "all", label: "All events" },
              { value: "verification", label: "Verifications" },
              { value: "decision", label: "Decisions" },
            ],
            predicate: (event, value) => event.action.startsWith(value),
          },
        ]}
        defaultSort={{ key: "when", dir: "desc" }}
        countNoun={["event", "events"]}
        loadingMessage="Loading the audit log…"
        noMatchMessage="No events match your filters."
        emptyState={
          <p className="px-[18px] py-10 text-center text-[13.5px] text-fed-gray">
            No activity recorded yet.
          </p>
        }
      />
    </div>
  );
}
