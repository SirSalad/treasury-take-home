import { CheckCircle2 } from "lucide-react";
import * as React from "react";

import { ApplicationForm } from "@/components/application/ApplicationForm";
import { Button } from "@/components/ui/button";
import type { ApplicationForm as ApplicationFormData } from "@/lib/application";

/**
 * Single-label verification page. For now it hosts the application entry form
 * (the "expected" data). Uploading artwork and rendering the color-coded
 * comparison are wired up in a later issue (tth-cwmn); until then a successful
 * submit confirms the captured application so the form is usable on its own.
 */
export function VerifyPage() {
  const [submitted, setSubmitted] = React.useState<ApplicationFormData | null>(null);

  if (submitted) {
    return (
      <div className="space-y-6">
        <div
          className="flex items-start gap-3 rounded-md border border-match bg-match-muted p-4"
          role="status"
        >
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-match" aria-hidden="true" />
          <div className="space-y-1">
            <h2 className="font-bold text-foreground">Application captured</h2>
            <p className="text-sm text-muted-foreground">
              Next, upload the label artwork to compare it against{" "}
              <span className="font-semibold">{submitted.brandName}</span>. Label upload and the
              side-by-side comparison land in a later iteration.
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={() => setSubmitted(null)}>
          Edit application
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Enter the application</h2>
        <p className="max-w-2xl text-muted-foreground">
          These are the details from the TTB label application (Form 5100.31). The app checks the
          uploaded label against them. Only a few fields are required — fill in what you have.
        </p>
      </header>
      <ApplicationForm onSubmit={setSubmitted} />
    </div>
  );
}
