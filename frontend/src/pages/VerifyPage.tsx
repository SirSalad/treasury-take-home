import { AlertCircle } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApplicationForm } from "@/components/application/ApplicationForm";
import { LabelUpload } from "@/components/application/LabelUpload";
import { ApiError, api } from "@/lib/api";
import {
  EMPTY_APPLICATION_FORM,
  type ApplicationForm as ApplicationFormData,
} from "@/lib/application";

/** The single-label flow's lifecycle: collect input, run, hand off to review. */
type Phase = { name: "input" } | { name: "submitting" } | { name: "error"; message: string };

/**
 * New Label Verification (claude-design): the agent enters the expected COLA
 * application data, uploads the label artwork, and submits. While the backend
 * reads the label an animated scanning card shows; on success the flow lands
 * on the review screen for that submission, where the verdict and the decision
 * panel live. On a bad upload, a friendly error invites another try without
 * losing the entered data.
 */
export function VerifyPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = React.useState<Phase>({ name: "input" });
  const [form, setForm] = React.useState<ApplicationFormData>(EMPTY_APPLICATION_FORM);
  const [images, setImages] = React.useState<File[]>([]);
  const [imageError, setImageError] = React.useState<string | undefined>();
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  // Hold an object URL for the first image so the scanning card can preview it.
  React.useEffect(() => {
    if (!images.length) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(images[0]);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [images]);

  // Abort an in-flight request if the user navigates away mid-verification.
  const abortRef = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => abortRef.current?.abort(), []);

  async function runVerification(values: ApplicationFormData) {
    if (!images.length) {
      setImageError("Add at least one label image to verify against the application.");
      return;
    }
    setImageError(undefined);
    setForm(values);

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase({ name: "submitting" });
    try {
      const response = await api.verify(images, values, controller.signal);
      navigate(`/review/${response.submission_id}`);
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

  if (phase.name === "submitting") {
    return (
      <div className="mx-auto max-w-[620px] py-14" role="status" aria-live="polite">
        <div className="rounded-[14px] border border-[#d6d7d9] bg-white p-[34px] text-center shadow-[0_10px_30px_rgba(17,46,81,.08)]">
          <div
            className="relative mx-auto mb-6 w-[230px] overflow-hidden rounded-md border border-[#d9d4c4]"
            style={{ aspectRatio: ".78" }}
          >
            {previewUrl ? (
              <img
                src={previewUrl}
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
              />
            ) : (
              <div className="absolute inset-0 bg-gradient-to-br from-[#f3ead2] to-[#e9dcbd]" />
            )}
            <div
              aria-hidden="true"
              className="absolute left-0 right-0 h-[3px]"
              style={{
                background: "linear-gradient(90deg, transparent, #226e2a, transparent)",
                boxShadow: "0 0 14px 3px rgba(46,133,64,.55)",
                animation: "scanmove 1.1s linear infinite",
              }}
            />
          </div>
          <p className="mb-1.5 text-[19px] font-extrabold text-fed-navy">Verifying the label…</p>
          <p className="text-sm text-fed-gray">
            Extracting the label text and comparing it to the application. Filings with several
            images can take up to a minute.
          </p>
        </div>
        {/* The scan-line keyframes live with the page that uses them. */}
        <style>{`@keyframes scanmove { 0% { top: 2%; } 100% { top: 96%; } }`}</style>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[980px] pb-10">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-fed-blue"
      >
        ← Back to Queue
      </Link>
      <h2 className="mb-1.5 text-[30px] font-extrabold tracking-[-.6px] text-fed-navy">
        New Label Verification
      </h2>
      <p className="mb-6 text-[14.5px] text-fed-gray">
        Enter the application data from TTB Form 5100.31 and upload the label images.
      </p>

      {phase.name === "error" && (
        <div
          role="alert"
          className="mb-6 flex items-start gap-3 rounded-xl border border-[#f3c9cb] bg-[#fef6f6] p-4"
        >
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-fed-red" aria-hidden="true" />
          <div className="space-y-1">
            <h3 className="font-bold text-fed-red-deep">Could not verify the label</h3>
            <p className="text-sm text-fed-ink">{phase.message}</p>
            <p className="text-sm text-fed-gray">
              The form entries below are unchanged. Correct the fields or images and resubmit.
            </p>
          </div>
        </div>
      )}

      <section className="mb-7">
        <h3 className="mb-2 text-lg font-bold text-fed-ink">Label artwork</h3>
        <p className="mb-2 text-sm text-fed-gray">
          Upload every label image in the filing (front, back, neck). Required items are split
          across labels — the Government Warning is usually on the back — so the full set is needed
          to check all fields.
        </p>
        <LabelUpload value={images} onChange={setImages} error={imageError} />
      </section>

      <ApplicationForm initialValue={form} onSubmit={runVerification} />
    </div>
  );
}
