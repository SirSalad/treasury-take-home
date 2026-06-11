/**
 * The verification-result contract returned by `POST /api/verify`, mirrored on
 * the client.
 *
 * The wire shapes are **generated** from the backend's OpenAPI spec
 * (`pnpm gen:api` -> `src/lib/api.gen.ts`, from `backend/openapi.json`) and
 * re-exported here under their established names, so the client can never
 * silently drift from the FastAPI/pydantic models — CI regenerates both
 * artefacts and fails on any diff. This module keeps only the names and the
 * small display helpers the comparison view needs.
 */

import type { components } from "@/lib/api.gen";
import type { VerificationStatus } from "@/lib/status";

type Schemas = components["schemas"];

/** Wire-shape version; bumped by the backend when the contract changes. */
export const RESULT_SCHEMA_VERSION = 2;

export type FieldStatus = Schemas["FieldStatus"];
export type OverallVerdict = Schemas["OverallVerdict"];
export type WarningVerdict = Schemas["WarningVerdict"];
export type SubmissionStatus = Schemas["SubmissionStatus"];
export type BoundingBox = Schemas["BoundingBox"];
export type SourceSpan = Schemas["SourceSpan"];
export type FieldResult = Schemas["FieldResult"];
export type GovernmentWarningResult = Schemas["GovernmentWarningResult"];
export type VerdictSummary = Schemas["VerdictSummary"];
export type VerificationResult = Schemas["VerificationResult"];
export type TimingInfo = Schemas["TimingInfo"];
export type ImageQuality = Schemas["ImageQuality"];
export type VerificationImageInfo = Schemas["VerificationImageInfo"];
export type VerificationResponse = Schemas["VerificationResponse"];

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
