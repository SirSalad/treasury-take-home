/**
 * Typed client for the TTB Label Verification backend (FastAPI).
 *
 * Requests go to a configurable base URL. In dev, the default `/api` prefix is
 * proxied to http://localhost:8000 by Vite (see vite.config.ts); in a built /
 * containerized deployment, set `VITE_API_BASE_URL`. Keeping everything
 * same-origin by default sidesteps CORS and the agency's outbound firewall.
 */

import type { components } from "@/lib/api.gen";
import type { ApplicationForm } from "@/lib/application";
import type { VerificationResponse, VerificationResult } from "@/lib/verification";

type ApiSchemas = components["schemas"];

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

// ---- Response shapes (generated from the backend's OpenAPI spec) ---------
// `pnpm gen:api` regenerates src/lib/api.gen.ts from backend/openapi.json;
// these aliases keep the established names. CI fails when either is stale.

export type HealthResponse = { status: string; version: string };

/** The reviewer's recorded judgment on a submission. */
export type ReviewDecision = ApiSchemas["ReviewDecision"];

/** One row of the review queue (mirrors `SubmissionRow` on the backend). */
export type SubmissionRow = ApiSchemas["SubmissionRow"];

/** Queue counts for the stat cards (mirrors `QueueStats`). */
export type QueueStats = ApiSchemas["QueueStats"];

/** One image of a submission's label set (mirrors `SubmissionImageRow`). */
export type SubmissionImageRow = ApiSchemas["SubmissionImageRow"];

/**
 * Full submission detail: queue row + persisted result + application. The
 * backend stores `result` as an opaque JSON column, so the spec types it
 * loosely; the client refines it to the result contract it actually is.
 */
export type SubmissionDetail = Omit<ApiSchemas["SubmissionDetail"], "result"> & {
  result: VerificationResult | null;
};

/** One row of the append-only audit trail (mirrors `AuditEventRow`). */
export type AuditEvent = ApiSchemas["AuditEventRow"];

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

  /**
   * Submissions for the review queue, newest first. Fetches the full window
   * (up to the API cap) — search, filters, and pagination are client-side, so
   * they must cover the whole queue, not one server page.
   */
  submissions(signal?: AbortSignal): Promise<SubmissionRow[]> {
    return request<SubmissionRow[]>("/submissions?limit=1000", { signal });
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
    // Scoped to one submission for the activity timeline; otherwise the full
    // log window (client-side search/pagination needs the whole set).
    const query = submissionId != null ? `?submission_id=${submissionId}` : "?limit=2000";
    return request<AuditEvent[]>(`/audit${query}`, { signal });
  },
};
