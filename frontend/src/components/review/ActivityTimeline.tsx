import { useEffect, useState } from "react";

import { api, type AuditEvent } from "@/lib/api";
import { describeAuditEvent, formatAuditTime } from "@/lib/audit";

/**
 * The audit trail for a single submission, shown on the review screen as a
 * compact vertical timeline so a reviewer can see this label's full history —
 * when it was verified, and every decision recorded on it — without leaving
 * the page. Reads the same append-only `/api/audit` trail, scoped by id.
 */
export function ActivityTimeline({ submissionId }: { submissionId: number }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .audit(submissionId, controller.signal)
      .then(setEvents)
      .catch(() => setEvents([])); // history is supplementary; never block the page
    return () => controller.abort();
  }, [submissionId]);

  if (!events || events.length === 0) return null;

  // The trail comes back newest-first; a timeline reads better oldest-first.
  const ordered = [...events].reverse();

  return (
    <section
      aria-label="Activity history"
      className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card"
    >
      <h3 className="border-b border-[#e6e8ea] px-[18px] py-[13px] text-[14.5px] font-extrabold text-fed-navy">
        Activity
      </h3>
      <ol className="px-[18px] py-3">
        {ordered.map((event, i) => {
          const view = describeAuditEvent(event);
          const last = i === ordered.length - 1;
          return (
            <li key={event.id} className="relative flex gap-3 pb-3 last:pb-0">
              {!last && (
                <span
                  aria-hidden="true"
                  className="absolute left-[5px] top-4 h-full w-px bg-fed-line"
                />
              )}
              <span
                aria-hidden="true"
                className="relative mt-1 h-[11px] w-[11px] flex-none rounded-full border-2 border-white"
                style={{ background: view.color, boxShadow: "0 0 0 1px " + view.color }}
              />
              <div className="min-w-0">
                <div className="text-[13px] font-bold text-fed-ink">{view.label}</div>
                {view.summary && <div className="text-[12px] text-fed-slate">{view.summary}</div>}
                <div className="text-[11px] tabular-nums text-fed-gray-light">
                  {formatAuditTime(event.created_at)}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
