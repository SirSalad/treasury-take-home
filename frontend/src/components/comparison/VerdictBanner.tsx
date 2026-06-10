import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  OVERALL_VERDICT_COLOR,
  OVERALL_VERDICT_LABEL,
  type OverallVerdict,
  type VerdictSummary,
} from "@/lib/verification";

const ICONS: Record<OverallVerdict, typeof CheckCircle2> = {
  pass: CheckCircle2,
  warning: AlertTriangle,
  fail: XCircle,
};

// Per-verdict surface styling. Each pairs a tinted background with a solid
// left accent so the verdict reads at a glance — but the icon and heading
// carry the meaning too, so it never depends on color alone (Section 508).
const SURFACE: Record<OverallVerdict, string> = {
  pass: "border-match bg-match-muted",
  warning: "border-warning bg-warning-muted",
  fail: "border-mismatch bg-mismatch-muted",
};

const ACCENT: Record<OverallVerdict, string> = {
  pass: "text-match",
  warning: "text-warning",
  fail: "text-mismatch",
};

interface VerdictBannerProps {
  verdict: OverallVerdict;
  /** Headline rationale explaining why the verdict came out this way. */
  rationale?: string;
  /** Per-status counts, shown as a compact at-a-glance summary. */
  summary?: VerdictSummary;
  className?: string;
}

/**
 * The big, obvious headline for a verification result. Large type, a status
 * icon, the verdict word, and a plain-language rationale — the first thing an
 * agent should see and understand without reading the table below.
 */
export function VerdictBanner({ verdict, rationale, summary, className }: VerdictBannerProps) {
  const Icon = ICONS[verdict];
  const color = OVERALL_VERDICT_COLOR[verdict];

  return (
    <div
      role="status"
      aria-label={`Verification ${OVERALL_VERDICT_LABEL[verdict]}`}
      className={cn(
        "flex flex-col gap-3 rounded-lg border-2 p-5 sm:flex-row sm:items-center sm:gap-5",
        SURFACE[verdict],
        className,
      )}
      data-verdict={verdict}
    >
      <Icon className={cn("size-10 shrink-0", ACCENT[verdict])} aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Verification result
        </p>
        <h2 className="text-3xl font-bold leading-tight text-foreground">
          {OVERALL_VERDICT_LABEL[verdict]}
        </h2>
        {rationale && <p className="text-base text-foreground/80">{rationale}</p>}
      </div>
      {summary && (
        <dl className="flex shrink-0 gap-4 sm:flex-col sm:gap-1 sm:text-right">
          <SummaryCount label="Matched" value={summary.match} className={ACCENT.pass} />
          <SummaryCount
            label="To review"
            value={summary.soft_warning}
            className={ACCENT.warning}
          />
          <SummaryCount label="Mismatched" value={summary.mismatch} className={ACCENT.fail} />
        </dl>
      )}
    </div>
  );
}

function SummaryCount({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className: string;
}) {
  return (
    <div className="flex items-baseline gap-1.5 sm:justify-end">
      <dt className="order-2 text-sm text-muted-foreground sm:order-1">{label}</dt>
      <dd className={cn("order-1 text-lg font-bold tabular-nums sm:order-2", className)}>
        {value}
      </dd>
    </div>
  );
}
