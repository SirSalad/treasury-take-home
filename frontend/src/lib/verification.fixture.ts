/**
 * A representative {@link VerificationResult} for tests and local rendering.
 *
 * Mirrors the kind of output the engine produces for a real label: a clean
 * match, a soft warning (case-only difference), a hard mismatch, a not-checked
 * field, and an altered Government Health Warning — so the comparison view can
 * be exercised across every status it must render.
 */

import type { VerificationResult } from "@/lib/verification";

export const SAMPLE_RESULT: VerificationResult = {
  schema_version: 1,
  overall: "fail",
  rationale: "Net contents on the label do not match the application.",
  summary: { match: 2, soft_warning: 1, mismatch: 1, not_checked: 1 },
  fields: [
    {
      field: "brand_name",
      status: "match",
      expected: "Stone's Throw",
      found: "Stone's Throw",
      score: 1.0,
      span: { line_index: 0, start: 0, end: 12 },
      box: { x_min: 120, y_min: 40, x_max: 480, y_max: 110 },
      reason: "Exact match.",
    },
    {
      field: "class_type",
      status: "soft_warning",
      expected: "Kentucky Straight Bourbon Whiskey",
      found: "KENTUCKY STRAIGHT BOURBON WHISKEY",
      score: 0.97,
      span: { line_index: 2, start: 0, end: 33 },
      box: { x_min: 90, y_min: 130, x_max: 520, y_max: 175 },
      reason: "Matches after normalizing case.",
    },
    {
      field: "alcohol_content",
      status: "match",
      expected: "45% Alc./Vol.",
      found: "45% ALC./VOL.",
      score: 0.98,
      span: { line_index: 4, start: 0, end: 13 },
      box: { x_min: 200, y_min: 320, x_max: 400, y_max: 360 },
      reason: "Matches after normalizing case.",
    },
    {
      field: "net_contents",
      status: "mismatch",
      expected: "750 mL",
      found: "375 mL",
      score: 0.4,
      span: { line_index: 5, start: 0, end: 6 },
      box: { x_min: 220, y_min: 380, x_max: 380, y_max: 420 },
      reason: "Label states a different net contents than the application.",
    },
    {
      field: "country_of_origin",
      status: "not_checked",
      expected: null,
      found: null,
      score: 0.0,
      span: null,
      box: null,
      reason: "Not supplied on the application.",
    },
  ],
  government_warning: {
    verdict: "altered",
    found_text:
      "Government Warning: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy...",
    header_all_caps: false,
    similarity: 0.93,
    issues: ["The “GOVERNMENT WARNING:” header is not in all capitals."],
    limitations: [
      "Bold type and minimum font size (27 CFR 16.22) are not verifiable from OCR text alone.",
    ],
    span: { line_index: 8, start: 0, end: 20 },
    box: { x_min: 60, y_min: 460, x_max: 540, y_max: 560 },
  },
};
