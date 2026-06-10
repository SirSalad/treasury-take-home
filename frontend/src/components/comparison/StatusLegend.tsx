import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import { VERIFICATION_STATUSES } from "@/lib/status";

const BLURB: Record<(typeof VERIFICATION_STATUSES)[number], string> = {
  match: "Label agrees with the application.",
  warning: "Agrees after normalizing case/punctuation, or needs a human glance.",
  mismatch: "Label contradicts the application.",
};

/**
 * Compact key for the color-coded comparison. Pairs each status color with its
 * badge (icon + word) and a one-line meaning, so the result screen is
 * self-explanatory and color is never the sole signal (Section 508 / WCAG 1.4.1).
 */
export function StatusLegend({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md border bg-card p-3", className)}>
      <p className="mb-2 text-sm font-semibold text-foreground">How fields are flagged</p>
      <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-6">
        {VERIFICATION_STATUSES.map((status) => (
          <li key={status} className="flex items-center gap-2 text-sm text-muted-foreground">
            <StatusBadge status={status} />
            <span>{BLURB[status]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
