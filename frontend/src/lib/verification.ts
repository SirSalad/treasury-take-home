/**
 * The verification-result contract returned by `POST /api/verify`, mirrored on
 * the client.
 *
 * These shapes track `app.verify.schemas` and `app.api.schemas` on the backend
 * (the stable JSON contract the comparison UI and batch results consume). String
 * enum values are kept identical so a parsed response maps straight onto these
 * types — see `RESULT_SCHEMA_VERSION` for the compatibility marker.
 *
 * The fetch wiring that produces a {@link VerificationResponse} lives with the
 * single-flow page; this module owns only the shapes and the small helpers the
 * comparison view needs (status → color mapping, field display labels).
 */

import type { VerificationStatus } from "@/lib/status";

/** Wire-shape version; bumped by the backend when the contract changes. */
export const RESULT_SCHEMA_VERSION = 2;

/** Per-field outcome of comparing the label against the application. */
export type FieldStatus = "match" | "soft_warning" | "mismatch" | "not_checked";

/** Roll-up verdict for a whole label. */
export type OverallVerdict = "pass" | "warning" | "fail";

/** Outcome of the dedicated Government Health Warning check. */
export type WarningVerdict = "compliant" | "altered" | "missing";

/** Submission lifecycle status (mirrors `app.models.enums.SubmissionStatus`). */
export type SubmissionStatus = "pending" | "processing" | "completed" | "failed";

/**
 * Axis-aligned bounding box in the original image's pixel coordinate space.
 * Overlays scale these against the rendered image's natural dimensions.
 */
export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

/** Character span within an OCR line, for highlighting the matched substring. */
export interface SourceSpan {
  line_index: number | null;
  start: number;
  end: number;
}

/** One field's verification result — a row of the comparison. */
export interface FieldResult {
  field: string;
  status: FieldStatus;
  expected: string | null;
  found: string | null;
  score: number;
  span: SourceSpan | null;
  box: BoundingBox | null;
  /** Which of the submission's images carried this verdict (null = single image). */
  image_index: number | null;
  reason: string;
}

/** Result of verifying one label's Government Health Warning. */
export interface GovernmentWarningResult {
  verdict: WarningVerdict;
  found_text: string | null;
  header_all_caps: boolean | null;
  similarity: number;
  issues: string[];
  limitations: string[];
  span: SourceSpan | null;
  box: BoundingBox | null;
  /** Which of the submission's images carried this verdict (null = single image). */
  image_index: number | null;
}

/** Counts of per-field statuses — a quick at-a-glance roll-up. */
export interface VerdictSummary {
  match: number;
  soft_warning: number;
  mismatch: number;
  not_checked: number;
}

/** The complete verification output for one label. */
export interface VerificationResult {
  schema_version: number;
  overall: OverallVerdict;
  fields: FieldResult[];
  government_warning: GovernmentWarningResult;
  summary: VerdictSummary;
  rationale: string;
}

/** Where wall-clock time went, so the 5s budget is visible. */
export interface TimingInfo {
  total_ms: number;
  ocr_ms: number;
}

/** How readable the uploaded image was, for retake guidance. */
export interface ImageQuality {
  level: "ok" | "low";
  mean_confidence: number;
  text_regions: number;
  message: string | null;
}

/** One image of the verified filing, with its readability grade. */
export interface VerificationImageInfo {
  index: number;
  filename: string | null;
  quality: ImageQuality;
}

/** The full `POST /api/verify` response. */
export interface VerificationResponse {
  submission_id: number;
  application_id: number | null;
  status: SubmissionStatus;
  image_filename: string | null;
  images: VerificationImageInfo[];
  timing: TimingInfo;
  result: VerificationResult;
  /** Worst readability across the uploaded images (retake guidance). */
  image_quality: ImageQuality;
}

// ---- Display helpers ----------------------------------------------------

/**
 * Map a per-field status onto the three-color {@link VerificationStatus}
 * vocabulary used by badges and overlays. `soft_warning` and `not_checked`
 * both fold into a non-failing state, but they are distinguished by label and
 * icon elsewhere (color is never the only signal — Section 508).
 */
export const FIELD_STATUS_COLOR: Record<FieldStatus, VerificationStatus> = {
  match: "match",
  soft_warning: "warning",
  mismatch: "mismatch",
  // Nothing to compare against; rendered neutrally rather than as a pass.
  not_checked: "warning",
};

/** The Government Health Warning verdict mapped onto the shared color trio. */
export const WARNING_VERDICT_COLOR: Record<WarningVerdict, VerificationStatus> = {
  compliant: "match",
  altered: "warning",
  missing: "mismatch",
};

/** Headline color + copy for the overall roll-up banner. */
export const OVERALL_VERDICT_COLOR: Record<OverallVerdict, VerificationStatus> = {
  pass: "match",
  warning: "warning",
  fail: "mismatch",
};

export const OVERALL_VERDICT_LABEL: Record<OverallVerdict, string> = {
  pass: "Passed",
  warning: "Needs review",
  fail: "Failed",
};

export const WARNING_VERDICT_LABEL: Record<WarningVerdict, string> = {
  compliant: "Compliant",
  altered: "Altered",
  missing: "Missing",
};

/**
 * Human-readable label for a per-field comparison key. Falls back to a
 * title-cased version of the raw key so a new backend field still renders
 * sensibly before this map is updated.
 */
const FIELD_LABELS: Record<string, string> = {
  brand_name: "Brand name",
  fanciful_name: "Fanciful name",
  class_type: "Class / type",
  alcohol_content: "Alcohol content",
  abv: "Alcohol by volume",
  proof: "Proof",
  net_contents: "Net contents",
  name_and_address: "Name & address",
  country_of_origin: "Country of origin",
  appellation: "Appellation",
  vintage: "Vintage",
};

export function fieldLabel(field: string): string {
  return (
    FIELD_LABELS[field] ??
    field
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

/** Plain-language description of what a per-field status means. */
export const FIELD_STATUS_LABEL: Record<FieldStatus, string> = {
  match: "Match",
  soft_warning: "Review",
  mismatch: "Mismatch",
  not_checked: "Not checked",
};
