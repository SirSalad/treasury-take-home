/**
 * Typed client for the TTB Label Verification backend (FastAPI).
 *
 * Requests go to a configurable base URL. In dev, the default `/api` prefix is
 * proxied to http://localhost:8000 by Vite (see vite.config.ts); in a built /
 * containerized deployment, set `VITE_API_BASE_URL`. Keeping everything
 * same-origin by default sidesteps CORS and the agency's outbound firewall.
 */

import type { ApplicationForm } from "@/lib/application";
import type { VerificationResponse } from "@/lib/verification";

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

function buildVerifyForm(image: File, application: ApplicationForm): FormData {
  const data = new FormData();
  data.append("image", image);
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

// ---- Endpoints ----------------------------------------------------------

export const api = {
  /** Liveness/readiness probe. */
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return request<HealthResponse>("/health", { signal });
  },

  /**
   * Verify one label image against its expected COLA application data. Sends a
   * multipart request to `POST /api/verify` and returns the verdict contract.
   */
  verify(
    image: File,
    application: ApplicationForm,
    signal?: AbortSignal,
  ): Promise<VerificationResponse> {
    return request<VerificationResponse>("/verify", {
      method: "POST",
      body: buildVerifyForm(image, application),
      signal,
    });
  },
};
