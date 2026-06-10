/**
 * Verification status vocabulary shared across the app.
 *
 * Every field comparison resolves to one of three states, color-coded
 * consistently everywhere (see the `match` / `warning` / `mismatch` design
 * tokens in `tailwind.config.ts`):
 *
 * - `match`    — label text agrees with the application (green)
 * - `warning`  — agrees after normalization, or needs a human eye (gold)
 *                e.g. "STONE'S THROW" vs "Stone's Throw"
 * - `mismatch` — label text contradicts the application (red)
 */
export type VerificationStatus = "match" | "warning" | "mismatch";

export const VERIFICATION_STATUSES: readonly VerificationStatus[] = [
  "match",
  "warning",
  "mismatch",
] as const;

/** Human-readable label for a status, for badges and screen readers. */
export const STATUS_LABEL: Record<VerificationStatus, string> = {
  match: "Match",
  warning: "Review",
  mismatch: "Mismatch",
};
