import { useState } from "react";

import type { ReviewDecision } from "@/lib/api";
import type { OverallVerdict } from "@/lib/verification";

/**
 * Review Decision panel (claude-design): the reviewer's three actions as a
 * radio group, an internal note, and the submit button. The recommended
 * action follows the automated verdict but never auto-submits — the human
 * always makes the call.
 */

const ACTIONS: Array<{ value: ReviewDecision; title: string; sub: string }> = [
  { value: "approve", title: "Approve label", sub: "All requirements met" },
  { value: "request_changes", title: "Request changes", sub: "Send back for correction" },
  { value: "request_info", title: "Request more info", sub: "Ask the applicant a question" },
];

const RECOMMENDED: Record<OverallVerdict, ReviewDecision> = {
  pass: "approve",
  warning: "request_info",
  fail: "request_changes",
};

interface DecisionPanelProps {
  overall: OverallVerdict | null;
  /** Already-recorded decision, when re-opening a decided submission. */
  recorded: { decision: ReviewDecision; note: string | null; decidedAt: string | null } | null;
  submitting: boolean;
  onSubmit: (decision: ReviewDecision, note: string) => void;
  onReturn: () => void;
}

export function DecisionPanel({
  overall,
  recorded,
  submitting,
  onSubmit,
  onReturn,
}: DecisionPanelProps) {
  const recommended = overall ? RECOMMENDED[overall] : null;
  const [choice, setChoice] = useState<ReviewDecision | null>(recorded?.decision ?? recommended);
  const [note, setNote] = useState(recorded?.note ?? "");

  return (
    <section
      aria-label="Review decision"
      className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card lg:sticky lg:top-24"
    >
      <h3 className="border-b border-[#e6e8ea] px-[18px] py-2.5 text-[14.5px] font-extrabold text-fed-navy">
        Review Decision
      </h3>
      <div className="px-[18px] py-3">
        {recorded && (
          <p className="mb-3 rounded-md border border-[#bfe0c6] bg-fed-green-wash px-3 py-2 text-[12.5px] font-semibold text-[#1e5a2d]">
            Decision recorded
            {recorded.decidedAt
              ? ` on ${new Date(recorded.decidedAt).toLocaleDateString("en-US")}`
              : ""}
            . You can revise it below.
          </p>
        )}
        <div role="radiogroup" aria-label="Decision" className="space-y-1.5">
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-[.5px] text-fed-gray-light">
            {recommended ? "Recommended" : "Choose an action"}
          </div>
          {ACTIONS.map((action) => {
            const selected = choice === action.value;
            return (
              <button
                type="button"
                role="radio"
                aria-checked={selected}
                key={action.value}
                onClick={() => setChoice(action.value)}
                className={`flex w-full items-center gap-3 rounded-lg border-2 px-3.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  selected
                    ? "border-fed-green bg-[#f3f8f4]"
                    : "border-fed-line bg-white hover:border-[#c8cdd2]"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex h-[18px] w-[18px] flex-none items-center justify-center rounded-full border-2 ${
                    selected ? "border-fed-green" : "border-[#a9aeb1]"
                  }`}
                >
                  {selected && <span className="h-2.5 w-2.5 rounded-full bg-fed-green" />}
                </span>
                <span>
                  <span className="block text-[13.5px] font-bold text-fed-ink">{action.title}</span>
                  <span className="mt-px block text-[11.5px] text-fed-gray">{action.sub}</span>
                </span>
              </button>
            );
          })}
        </div>

        <label htmlFor="decision-note" className="mb-1 mt-3 block text-xs font-bold text-fed-slate">
          Internal note{" "}
          <span className="font-normal text-fed-gray-light">(not sent to applicant)</span>
        </label>
        <textarea
          id="decision-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add a note for the record..."
          className="min-h-[56px] w-full resize-y rounded-md border border-[#c4c8cc] px-[11px] py-2 text-[13px] text-fed-ink focus:outline focus:outline-[3px] focus:outline-[#2491ff]"
        />
        <button
          type="button"
          disabled={!choice || submitting}
          onClick={() => choice && onSubmit(choice, note)}
          className="mt-3 w-full rounded-md bg-fed-blue p-2.5 text-[15px] font-extrabold text-white shadow-[0_1px_0_rgba(0,0,0,.12)] hover:bg-[#0b4778] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Recording…" : "Submit Decision"}
        </button>
        <button
          type="button"
          onClick={onReturn}
          className="mt-1.5 w-full rounded-md p-1.5 text-sm font-bold text-fed-blue hover:underline"
        >
          Return to queue
        </button>
      </div>
    </section>
  );
}
