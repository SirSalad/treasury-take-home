/**
 * Typed client for the TTB Label Verification backend (FastAPI).
 *
 * Requests go to a configurable base URL. In dev, the default `/api` prefix is
 * proxied to http://localhost:8000 by Vite (see vite.config.ts); in a built /
 * containerized deployment, set `VITE_API_BASE_URL`. Keeping everything
 * same-origin by default sidesteps CORS and the agency's outbound firewall.
 */

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

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const init: RequestInit = { ...rest, headers: { ...headers } };

  if (body !== undefined) {
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
    throw new ApiError(response.status, `API request to ${path} failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
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
};
