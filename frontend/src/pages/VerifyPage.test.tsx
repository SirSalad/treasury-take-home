import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { SAMPLE_RESULT } from "@/lib/verification.fixture";
import type { VerificationResponse } from "@/lib/verification";
import { VerifyPage } from "./VerifyPage";

// Mock the API client so the flow can be driven without a backend.
const verify = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, verify: (...args: unknown[]) => verify(...args) } };
});

const RESPONSE: VerificationResponse = {
  submission_id: 42,
  application_id: 1,
  status: "completed",
  image_filename: "label.png",
  timing: { total_ms: 2400, ocr_ms: 1500 },
  result: SAMPLE_RESULT,
  image_quality: { level: "ok", mean_confidence: 0.97, text_regions: 11, message: null },
};

/** Render the page inside a router, with a probe route for the review screen. */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/verify"]}>
      <Routes>
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/" element={<p>queue probe</p>} />
        <Route path="/review/:id" element={<p>review probe</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Fill the three required fields and attach an image, then submit. */
function fillAndSubmit({ withImage = true }: { withImage?: boolean } = {}) {
  fireEvent.change(screen.getByLabelText(/Source/i), { target: { value: "domestic" } });
  fireEvent.change(screen.getByLabelText(/Product type/i), {
    target: { value: "distilled_spirits" },
  });
  fireEvent.change(screen.getByLabelText(/Brand name/i), { target: { value: "Stone's Throw" } });

  if (withImage) {
    const file = new File(["x"], "label.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
  }

  fireEvent.click(screen.getByRole("button", { name: /Verify label/i }));
}

beforeEach(() => {
  verify.mockReset();
  // jsdom has no object-URL support.
  globalThis.URL.createObjectURL = vi.fn(() => "blob:label");
  globalThis.URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("VerifyPage flow", () => {
  it("blocks submit and explains when no label image is attached", () => {
    renderPage();
    fillAndSubmit({ withImage: false });
    expect(verify).not.toHaveBeenCalled();
    expect(screen.getByText(/Add the label image/i)).toBeDefined();
  });

  it("shows the scanning state then lands on the review screen on success", async () => {
    let resolve!: (value: VerificationResponse) => void;
    verify.mockReturnValue(new Promise<VerificationResponse>((r) => (resolve = r)));

    renderPage();
    fillAndSubmit();

    // Scanning state is announced while the request is in flight.
    expect(await screen.findByText(/Reading the label/i)).toBeDefined();

    resolve(RESPONSE);

    // Success hands off to the review screen for the new submission.
    expect(await screen.findByText(/review probe/i)).toBeDefined();
    expect(verify).toHaveBeenCalledOnce();
  });

  it("surfaces a friendly error and keeps the entered data on failure", async () => {
    verify.mockRejectedValue(new ApiError(422, "No text could be recognised in the image."));

    renderPage();
    fillAndSubmit();

    expect(await screen.findByText(/No text could be recognised/i)).toBeDefined();
    expect(screen.getByRole("heading", { name: /Could not verify the label/i })).toBeDefined();
    // The form is still present so the agent can adjust and retry.
    expect((screen.getByLabelText(/Brand name/i) as HTMLInputElement).value).toBe("Stone's Throw");
  });
});
