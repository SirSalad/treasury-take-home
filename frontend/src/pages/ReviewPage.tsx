import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ActivityTimeline } from "@/components/review/ActivityTimeline";
import { DecisionPanel } from "@/components/review/DecisionPanel";
import { ReviewChecklist } from "@/components/review/ReviewChecklist";
import { WarningHero } from "@/components/review/WarningHero";
import { LabelImage, type ImageRegion } from "@/components/comparison/LabelImage";
import { api, ApiError, type ReviewDecision, type SubmissionDetail } from "@/lib/api";
import {
  FIELD_STATUS_COLOR,
  WARNING_VERDICT_COLOR,
  fieldLabel,
  type OverallVerdict,
} from "@/lib/verification";

/** Stable region key for the Government Health Warning highlight box. */
const WARNING_KEY = "government_warning";

const VERDICT_PILL: Record<
  OverallVerdict,
  { icon: string; label: string; color: string; bg: string }
> = {
  pass: { icon: "✓", label: "All checks passed", color: "#226e2a", bg: "#eaf4ec" },
  warning: { icon: "⚠", label: "Needs review", color: "#7a5a00", bg: "#faf3d1" },
  fail: { icon: "✗", label: "Checks failed", color: "#b50909", bg: "#fdeced" },
};

/**
 * The review screen (claude-design): three aligned panes — the submitted label
 * with highlight boxes, the verification checklist with the Government Warning
 * hero, and the decision panel where the reviewer records their judgment.
 */
export function ReviewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const submissionId = Number(id);

  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [activeImage, setActiveImage] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(submissionId)) {
      setError("Invalid submission id.");
      return;
    }
    const controller = new AbortController();
    api
      .submission(submissionId, controller.signal)
      .then(setDetail)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not load this submission.");
      });
    return () => controller.abort();
  }, [submissionId]);

  const result = detail?.result ?? null;

  // The filing's label set; legacy details without an images list still show
  // their one image. Old results (schema v1) carry no image_index — treat as 0.
  const images = detail?.images?.length
    ? detail.images
    : [{ index: 0, filename: detail?.image_filename ?? null, kind: null }];

  const allRegions = useMemo<Array<ImageRegion & { imageIndex: number }>>(() => {
    if (!result) return [];
    const out: Array<ImageRegion & { imageIndex: number }> = [];
    for (const field of result.fields ?? []) {
      if (field.box) {
        out.push({
          key: field.field,
          box: field.box,
          status: FIELD_STATUS_COLOR[field.status],
          label: fieldLabel(field.field),
          imageIndex: field.image_index ?? 0,
        });
      }
    }
    if (result.government_warning.box) {
      out.push({
        key: WARNING_KEY,
        box: result.government_warning.box,
        status: WARNING_VERDICT_COLOR[result.government_warning.verdict],
        label: "Government Health Warning",
        imageIndex: result.government_warning.image_index ?? 0,
      });
    }
    return out;
  }, [result]);

  // Boxes are drawn only on the image they were found on.
  const regions = useMemo<ImageRegion[]>(
    () => allRegions.filter((region) => region.imageIndex === activeImage),
    [allRegions, activeImage],
  );

  // Numbered across the whole set (not per image) so checklist refs are stable.
  const regionNumbers = useMemo(() => {
    const numbers = new Map<string, number>();
    allRegions.forEach((region, index) => numbers.set(region.key, index + 1));
    return numbers;
  }, [allRegions]);

  const highlight = activeKey ?? selectedKey;

  // Selecting a checklist row (or a box) jumps to the image that carries it
  // and focuses it — the image auto-zooms and centers on the region.
  // Deselecting zooms back out to the fitted view.
  function selectKey(key: string) {
    const deselecting = selectedKey === key;
    setSelectedKey(deselecting ? null : key);
    if (deselecting) {
      setZoom(1);
      return;
    }
    const region = allRegions.find((r) => r.key === key);
    if (region) setActiveImage(region.imageIndex);
  }

  function submitDecision(decision: ReviewDecision, note: string) {
    setSubmitting(true);
    setDecisionError(null);
    api
      .recordDecision(submissionId, decision, note)
      .then(() => navigate("/", { replace: false }))
      .catch((err: unknown) => {
        setDecisionError(err instanceof ApiError ? err.message : "Could not record the decision.");
        setSubmitting(false);
      });
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[760px] py-10">
        <Link
          to="/"
          className="mb-4 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-fed-blue"
        >
          ← Back to Queue
        </Link>
        <div
          role="alert"
          className="rounded-xl border border-[#f3c9cb] bg-[#fef6f6] px-6 py-5 text-sm text-fed-red-deep"
        >
          {error}
        </div>
      </div>
    );
  }

  if (!detail) {
    return <p className="py-10 text-sm text-fed-gray">Loading submission…</p>;
  }

  // A failed submission has no result to review — show the unreadable screen.
  if (detail.status === "failed" || !result) {
    return (
      <div className="mx-auto max-w-[760px] py-6">
        <Link
          to="/verify"
          className="mb-4 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-fed-blue"
        >
          ← Try another image
        </Link>
        <div
          className="overflow-hidden rounded-xl border border-[#d6d7d9] bg-white"
          style={{ borderTop: "5px solid #cd2026" }}
        >
          <div className="px-[30px] py-7">
            <h2 className="mb-2 text-[21px] font-extrabold text-fed-red-deep">
              No text could be read from this filing
            </h2>
            <p className="mb-4 text-[14.5px] leading-[1.55] text-fed-slate">
              {detail.error ??
                "No text could be recognized in the uploaded image(s), so no fields were checked."}
            </p>
            <Link
              to="/verify"
              className="inline-block rounded-md bg-fed-blue px-5 py-2.5 text-sm font-bold text-white hover:bg-[#0b4778]"
            >
              Upload a clearer image
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const verdict = VERDICT_PILL[result.overall];
  const application = detail.application ?? {};
  const meta: Array<[string, string]> = [
    ["Submission", `SUB-${String(detail.id).padStart(4, "0")}`],
    ["Submitted", detail.created_at ? new Date(detail.created_at).toLocaleString("en-US") : "—"],
    ["Applicant", detail.applicant ?? "—"],
    ["Product Type", String(application.product_type ?? "—").replace(/_/g, " ")],
    ["Class / Type", detail.class_type ?? "—"],
    [
      images.length > 1 ? "Images" : "Image",
      images.length > 1 ? `${images.length} labels` : (detail.image_filename ?? "—"),
    ],
  ];

  return (
    <div className="pb-6">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3.5">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13.5px] font-semibold text-fed-blue"
          >
            ← Back to Queue
          </Link>
          <h2 className="whitespace-nowrap text-[23px] font-extrabold tracking-[-.4px] text-fed-navy">
            {detail.brand_name ?? "Untitled submission"}
          </h2>
          <span
            className="inline-flex items-center gap-2 whitespace-nowrap rounded-full px-[13px] py-1.5 text-[13px] font-bold"
            style={{ color: verdict.color, background: verdict.bg }}
          >
            <span aria-hidden="true" className="text-[15px]">
              {verdict.icon}
            </span>
            {verdict.label}
          </span>
          {detail.processing_ms != null && (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-fed-green-wash px-[11px] py-[5px] text-[12.5px] font-semibold text-fed-green">
              ⏱ Processed in {(detail.processing_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>
      </div>

      <dl className="mb-2.5 grid grid-cols-2 gap-x-4 gap-y-1 rounded-[10px] border border-fed-line bg-white px-4 py-2 shadow-card sm:grid-cols-3 lg:grid-cols-6">
        {meta.map(([key, value]) => (
          <div key={key} className="min-w-0">
            <dt className="text-[10px] font-bold uppercase tracking-[.5px] text-fed-gray-light">
              {key}
            </dt>
            <dd
              className="truncate text-[13px] font-semibold tabular-nums text-fed-ink"
              title={value}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,460px)_minmax(0,1fr)_320px]">
        {/* LEFT: submitted label with highlight boxes — sized to the viewport
            height so it fills the screen without pushing the page taller. */}
        <div className="flex flex-col overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
          <div className="flex items-center justify-between border-b border-[#e6e8ea] px-4 py-2.5">
            <h3 className="text-[13.5px] font-bold text-fed-navy">
              {images.length > 1 ? "Submitted Labels" : "Submitted Label"}
            </h3>
            <div className="flex gap-1.5">
              <button
                type="button"
                aria-label="Zoom out"
                onClick={() => setZoom((z) => Math.max(0.5, Math.round((z - 0.25) * 4) / 4))}
                className="h-7 w-7 rounded-[5px] border border-[#d6d7d9] bg-[#f7f8f9] text-base leading-none text-fed-gray hover:bg-fed-blue-wash"
              >
                −
              </button>
              <button
                type="button"
                aria-label="Zoom in"
                onClick={() => setZoom((z) => Math.min(4, Math.round((z + 0.25) * 4) / 4))}
                className="h-7 w-7 rounded-[5px] border border-[#d6d7d9] bg-[#f7f8f9] text-[15px] leading-none text-fed-gray hover:bg-fed-blue-wash"
              >
                +
              </button>
            </div>
          </div>
          {images.length > 1 && (
            <div
              role="tablist"
              aria-label="Label images"
              className="flex gap-1 border-b border-[#e6e8ea] bg-[#f7f8f9] px-3 py-1.5"
            >
              {images.map((img, i) => {
                const boxCount = allRegions.filter((r) => r.imageIndex === i).length;
                return (
                  <button
                    key={i}
                    type="button"
                    role="tab"
                    aria-selected={activeImage === i}
                    title={img.filename ?? undefined}
                    onClick={() => setActiveImage(i)}
                    className={
                      "rounded-md px-3 py-1 text-[12px] font-semibold " +
                      (activeImage === i
                        ? "bg-fed-blue text-white"
                        : "text-fed-gray hover:bg-fed-blue-wash")
                    }
                  >
                    Image {i + 1}
                    {img.kind ? ` · ${img.kind}` : ""}
                    {boxCount > 0 && (
                      <span className="ml-1.5 rounded-full bg-black/15 px-1.5 text-[10.5px] tabular-nums">
                        {boxCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
          {/* Layout-affecting zoom (no CSS transform): the image's real size
              grows, so this container gains true scroll range. The child uses
              m-auto (not justify/items-center) — flex-centering makes
              start-side overflow unreachable; auto margins center when the
              image fits and collapse cleanly when it overflows. */}
          <div className="flex max-h-[calc(100vh-230px)] overflow-auto bg-[#41464d] p-3">
            <LabelImage
              key={activeImage}
              src={api.submissionImageUrl(detail.id, activeImage)}
              alt={`Label image ${activeImage + 1} for ${detail.brand_name ?? "submission"}`}
              regions={regions}
              activeKey={highlight}
              focusKey={selectedKey}
              zoom={zoom}
              onAutoZoom={setZoom}
              onSelect={selectKey}
              className="m-auto"
              imgClassName="h-auto w-auto max-h-[calc(100vh-260px)]"
            />
          </div>
          <p className="flex items-center gap-[7px] border-t border-[#e6e8ea] px-4 py-2 text-[11px] text-fed-gray">
            <span
              aria-hidden="true"
              className="inline-block h-[9px] w-[9px] rounded-[2px] bg-fed-green"
            />
            {images.length > 1
              ? "Click a checklist row to jump to the image where it was found."
              : "Hover a checklist row to see where it was found on the label."}
          </p>
        </div>

        {/* MIDDLE: checklist + warning hero */}
        <div className="flex flex-col gap-3">
          <ReviewChecklist
            fields={result.fields ?? []}
            regionNumbers={regionNumbers}
            activeKey={highlight}
            onActivate={setActiveKey}
            onSelect={selectKey}
          />
          <WarningHero result={result.government_warning} />
        </div>

        {/* RIGHT: decision + activity, in normal flow so they scroll together
            (no sticky — the panel pinning while the timeline slid under it was
            the "Activity collapses on scroll" glitch). */}
        <div>
          {decisionError && (
            <div
              role="alert"
              className="mb-3 rounded-lg border border-[#f3c9cb] bg-[#fef6f6] px-3 py-2 text-[12.5px] text-fed-red-deep"
            >
              {decisionError}
            </div>
          )}
          <DecisionPanel
            overall={result.overall}
            recorded={
              detail.decision
                ? {
                    decision: detail.decision,
                    note: detail.decision_note,
                    decidedAt: detail.decided_at,
                  }
                : null
            }
            submitting={submitting}
            onSubmit={submitDecision}
            onReturn={() => navigate("/")}
          />
          <div className="mt-4">
            <ActivityTimeline submissionId={detail.id} />
          </div>
        </div>
      </div>
    </div>
  );
}
