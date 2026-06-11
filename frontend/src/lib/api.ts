/**
 * Typed client for the TTB Label Verification backend (FastAPI).
 *
 * Requests go to a configurable base URL. In dev, the default `/api` prefix is
 * proxied to http://localhost:8000 by Vite (see vite.config.ts); in a built /
 * containerized deployment, set `VITE_API_BASE_URL`. Keeping everything
 * same-origin by default sidesteps CORS and the agency's outbound firewall.
 */

import type { ApplicationForm } from "@/lib/application";
import type { VerificationResponse, VerificationResult } from "@/lib/verification";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

/** Error thrown when the API responds with a non-2xx status. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

/**
 * Pull a human-readable message out of a FastAPI error body. Validation errors
 * arrive as ``{ detail: [{ msg, loc }, ...] }``; deliberate 4xx responses as
 * ``{ detail: "..." }``. Falls back to a generic line when the body is opaque.
 */
async function errorMessage(response: Response, path: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const { detail } = body;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : null))
        .filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  } catch {
    // Non-JSON or empty body; fall through to the generic message.
  }
  return `API request to ${path} failed (${response.status})`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const init: RequestInit = { ...rest, headers: { ...headers } };

  if (body instanceof FormData) {
    // Let the browser set the multipart Content-Type (with its boundary).
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "Content-Type": "application/json", ...init.headers };
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch (cause) {
    throw new ApiError(0, `Network error reaching the API: ${String(cause)}`);
  }

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response, path));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * Map the camelCase {@link ApplicationForm} onto the backend's snake_case
 * multipart fields, omitting blanks so the server applies its own defaults.
 * `plantRegistryNumber` has no backend counterpart and is intentionally dropped.
 */
const FORM_FIELD_MAP: ReadonlyArray<[keyof ApplicationForm, string]> = [
  ["brandName", "brand_name"],
  ["source", "source"],
  ["productType", "product_type"],
  ["classType", "class_type"],
  ["alcoholContentPct", "alcohol_content_pct"],
  ["alcoholContentText", "alcohol_content_text"],
  ["netContents", "net_contents"],
  ["nameAndAddress", "name_and_address"],
  ["countryOfOrigin", "country_of_origin"],
  ["vintage", "vintage"],
  ["serialNumber", "serial_number"],
  ["fancifulName", "fanciful_name"],
  ["appellation", "appellation"],
];

function buildVerifyForm(images: File[], application: ApplicationForm): FormData {
  const data = new FormData();
  for (const image of images) data.append("images", image);
  for (const [formKey, apiKey] of FORM_FIELD_MAP) {
    const value = application[formKey].trim();
    if (value) data.append(apiKey, value);
  }
  return data;
}

// ---- Response shapes (mirror the backend) -------------------------------

export interface HealthResponse {
  status: string;
  version: string;
}

/** The reviewer's recorded judgment on a submission. */
export type ReviewDecision = "approve" | "request_changes" | "request_info";

/** One row of the review queue (mirrors `SubmissionRow` on the backend). */
export interface SubmissionRow {
  id: number;
  created_at: string | null;
  status: "pending" | "processing" | "completed" | "failed";
  brand_name: string | null;
  applicant: string | null;
  class_type: string | null;
  overall: "pass" | "warning" | "fail" | null;
  warning_verdict: "compliant" | "altered" | "missing" | null;
  processing_ms: number | null;
  image_filename: string | null;
  decision: ReviewDecision | null;
  decided_at: string | null;
}

/** Queue counts for the stat cards (mirrors `QueueStats`). */
export interface QueueStats {
  pending: number;
  flagged: number;
  cleared_week: number;
  avg_scan_ms: number | null;
}

/** One image of a submission's label set (mirrors `SubmissionImageRow`). */
export interface SubmissionImageRow {
  index: number;
  filename: string | null;
  kind: string | null;
}

/** Full submission detail: queue row + persisted result + application. */
export interface SubmissionDetail extends SubmissionRow {
  result: VerificationResult | null;
  error: string | null;
  decision_note: string | null;
  application: Record<string, string | number | null> | null;
  /** The filing's label set; the result's `image_index` values refer to these. */
  images: SubmissionImageRow[];
}

/** One row of the append-only audit trail (mirrors `AuditEventRow`). */
export interface AuditEvent {
  id: number;
  created_at: string | null;
  action: string;
  actor: string;
  submission_id: number | null;
  detail: Record<string, unknown> | null;
}

// ---- Endpoints ----------------------------------------------------------

export const api = {
  /** Liveness/readiness probe. */
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return request<HealthResponse>("/health", { signal });
  },

  /**
   * Verify a filing's label image set (front, back, …) against its expected
   * COLA application data. Sends a multipart request to `POST /api/verify`
   * (repeated `images` parts, in order) and returns the verdict contract.
   */
  verify(
    images: File[],
    application: ApplicationForm,
    signal?: AbortSignal,
  ): Promise<VerificationResponse> {
    return request<VerificationResponse>("/verify", {
      method: "POST",
      body: buildVerifyForm(images, application),
      signal,
    });
  },

  /** Recent submissions for the review queue, newest first. */
  submissions(signal?: AbortSignal): Promise<SubmissionRow[]> {
    return request<SubmissionRow[]>("/submissions", { signal });
  },

  /** Counts for the stat cards above the queue. */
  queueStats(signal?: AbortSignal): Promise<QueueStats> {
    return request<QueueStats>("/submissions/stats", { signal });
  },

  /** One submission with its persisted verification result. */
  submission(id: number, signal?: AbortSignal): Promise<SubmissionDetail> {
    return request<SubmissionDetail>(`/submissions/${id}`, { signal });
  },

  /** URL of a stored label image for a submission (for <img src>). */
  submissionImageUrl(id: number, index = 0): string {
    return `${BASE_URL}/submissions/${id}/images/${index}`;
  },

  /** Record the reviewer's decision on a submission. */
  recordDecision(
    id: number,
    decision: ReviewDecision,
    note: string | null,
    signal?: AbortSignal,
  ): Promise<SubmissionDetail> {
    return request<SubmissionDetail>(`/submissions/${id}/decision`, {
      method: "POST",
      body: { decision, note: note || null },
      signal,
    });
  },

  /** Append-only audit trail, newest first; optionally scoped to one submission. */
  audit(submissionId?: number, signal?: AbortSignal): Promise<AuditEvent[]> {
    const query = submissionId != null ? `?submission_id=${submissionId}` : "";
    return request<AuditEvent[]>(`/audit${query}`, { signal });
  },
};
