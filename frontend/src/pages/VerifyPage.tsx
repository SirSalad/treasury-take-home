import { AlertCircle, Loader2 } from "lucide-react";
import * as React from "react";

import { ApplicationForm } from "@/components/application/ApplicationForm";
import { LabelUpload } from "@/components/application/LabelUpload";
import { ComparisonView } from "@/components/comparison/ComparisonView";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import {
  EMPTY_APPLICATION_FORM,
  type ApplicationForm as ApplicationFormData,
} from "@/lib/application";
import type { VerificationResponse } from "@/lib/verification";

/** The single-label flow's lifecycle: collect input, run, show the verdict. */
type Phase =
  | { name: "input" }
  | { name: "submitting" }
  | { name: "result"; response: VerificationResponse }
  | { name: "error"; message: string };

/**
 * The single-label verification flow, end to end: the agent enters the expected
 * COLA application data, uploads the label artwork, and submits. While the
 * backend preprocesses, OCRs, and verifies, a loading state shows; on success
 * the color-coded 3-pane comparison renders with the wall-clock time; on a bad
 * upload or unreadable image, a friendly error invites another try without
 * losing the entered data.
 */
export function VerifyPage() {
  const [phase, setPhase] = React.useState<Phase>({ name: "input" });
  const [form, setForm] = React.useState<ApplicationFormData>(EMPTY_APPLICATION_FORM);
  const [image, setImage] = React.useState<File | null>(null);
  const [imageError, setImageError] = React.useState<string | undefined>();
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  // Hold an object URL for the selected image so it can be previewed in the
  // picker and reused as pane 3 of the comparison. Revoked when it changes.
  React.useEffect(() => {
    if (!image) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  // Abort an in-flight request if the user navigates away mid-verification.
  const abortRef = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => abortRef.current?.abort(), []);

  async function runVerification(values: ApplicationFormData) {
    if (!image) {
      setImageError("Add the label image to verify against the application.");
      return;
    }
    setImageError(undefined);
    setForm(values);

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase({ name: "submitting" });
    try {
      const response = await api.verify(image, values, controller.signal);
      setPhase({ name: "result", response });
    } catch (err) {
      if (controller.signal.aborted) return;
      const message =
        err instanceof ApiError
          ? err.status === 0
            ? "Could not reach the verification service. Check that the API is running and try again."
            : err.message
          : "Something went wrong while verifying the label. Please try again.";
      setPhase({ name: "error", message });
    }
  }

  function backToInput() {
    setPhase({ name: "input" });
  }

  if (phase.name === "result") {
    const { response } = phase;
    const seconds = (response.timing.total_ms / 1000).toFixed(1);
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              Verification result
            </h2>
            <p className="text-sm text-muted-foreground">
              {response.image_filename ? (
                <>
                  <span className="font-medium text-foreground">{response.image_filename}</span>{" "}
                  ·{" "}
                </>
              ) : null}
              Processed in {seconds}s
            </p>
          </div>
          <Button variant="outline" onClick={backToInput}>
            Verify another label
          </Button>
        </div>
        {previewUrl ? (
          <ComparisonView
            result={response.result}
            imageSrc={previewUrl}
            imageAlt={response.image_filename ?? "Uploaded label"}
          />
        ) : null}
      </div>
    );
  }

  if (phase.name === "submitting") {
    return (
      <div
        className="flex flex-col items-center justify-center gap-4 py-24 text-center"
        role="status"
        aria-live="polite"
      >
        <Loader2 className="size-10 animate-spin text-primary" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-lg font-semibold text-foreground">Verifying the label…</p>
          <p className="text-sm text-muted-foreground">
            Reading the artwork and comparing it against the application. This usually takes a few
            seconds.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Verify a label</h2>
        <p className="max-w-2xl text-muted-foreground">
          Enter the details from the TTB label application (Form 5100.31) and upload the label
          artwork. The app reads the label and checks it against what you entered, then shows a
          color-coded, side-by-side verdict.
        </p>
      </header>

      {phase.name === "error" && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-md border border-destructive bg-mismatch-muted p-4"
        >
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
          <div className="space-y-1">
            <h3 className="font-bold text-destructive">Could not verify the label</h3>
            <p className="text-sm text-foreground">{phase.message}</p>
            <p className="text-sm text-muted-foreground">
              Your entries are kept below — adjust them or the image and try again.
            </p>
          </div>
        </div>
      )}

      <section className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Label artwork</h3>
        <p className="text-sm text-muted-foreground">
          Upload a photo or scan of the physical label. This is the “actual” side of the comparison.
        </p>
        <LabelUpload value={image} onChange={setImage} previewUrl={previewUrl} error={imageError} />
      </section>

      <ApplicationForm initialValue={form} onSubmit={runVerification} />
    </div>
  );
}
