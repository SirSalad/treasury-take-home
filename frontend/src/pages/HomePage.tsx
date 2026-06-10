import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { ApiHealth } from "@/components/ApiHealth";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { VERIFICATION_STATUSES } from "@/lib/status";

const STATUS_BLURB: Record<(typeof VERIFICATION_STATUSES)[number], string> = {
  match: "The label text agrees with the application — nothing to do.",
  warning: "Agrees after normalizing punctuation or case — a quick human glance.",
  mismatch: "The label contradicts the application — needs attention.",
};

/** Themed landing page demonstrating the federal look and status color system. */
export function HomePage() {
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h2 className="text-3xl font-bold tracking-tight text-foreground">
          Verify alcohol labels in seconds
        </h2>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Enter the application details, upload the label artwork, and the app extracts the
          label&apos;s text and compares it field by field — flagging matches, warnings, and
          mismatches, with an exact check on the Government Health Warning.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button asChild size="lg">
            <Link to="/">
              Start a verification
              <ArrowRight />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/batch">Batch upload</Link>
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold">How results are flagged</h3>
        <ul className="grid gap-4 sm:grid-cols-3">
          {VERIFICATION_STATUSES.map((status) => (
            <li
              key={status}
              className="rounded-lg border bg-card p-4 shadow-sm"
              data-status={status}
            >
              <StatusBadge status={status} />
              <p className="mt-2 text-sm text-muted-foreground">{STATUS_BLURB[status]}</p>
            </li>
          ))}
        </ul>
      </section>

      <ApiHealth />
    </div>
  );
}
