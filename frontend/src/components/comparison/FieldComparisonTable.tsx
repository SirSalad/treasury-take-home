import { MapPin } from "lucide-react";

import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import { FIELD_STATUS_COLOR, fieldLabel, type FieldResult } from "@/lib/verification";

// Left accent bar color per status, so each row's verdict reads down the edge.
const ACCENT: Record<string, string> = {
  match: "border-l-match",
  warning: "border-l-warning",
  mismatch: "border-l-mismatch",
};

interface FieldComparisonTableProps {
  fields: FieldResult[];
  /** Key of the selected field row. */
  activeField?: string | null;
  onSelect?: (field: string) => void;
}

/**
 * The aligned expected-vs-extracted comparison. Each field is one row showing
 * the application's expected value beside what was recovered from the label,
 * with a color-coded status badge. Rows that locate a region on the image are
 * selectable — clicking one highlights that region (and a pin icon advertises
 * the link). Built as a description-list-like grid so the two value columns
 * stay aligned and the structure is announced to screen readers.
 */
export function FieldComparisonTable({
  fields,
  activeField,
  onSelect,
}: FieldComparisonTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className="grid grid-cols-[1fr_1fr] gap-px bg-border text-sm">
        <div className="bg-secondary px-4 py-2 font-semibold text-foreground">
          Application (expected)
        </div>
        <div className="bg-secondary px-4 py-2 font-semibold text-foreground">
          Extracted from label
        </div>
      </div>
      <ul className="divide-y">
        {fields.map((field) => {
          const color = FIELD_STATUS_COLOR[field.status];
          const isActive = field.field === activeField;
          const locatable = Boolean(field.box);
          const label = fieldLabel(field.field);

          const content = (
            <div
              className={cn(
                "grid grid-cols-[1fr_1fr] gap-x-4 border-l-4 px-4 py-3 text-left",
                ACCENT[color],
                isActive && "bg-accent/40",
              )}
            >
              <div className="min-w-0 space-y-0.5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {label}
                </p>
                <p className="break-words text-base text-foreground">
                  {field.expected ?? <span className="text-muted-foreground">—</span>}
                </p>
              </div>
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <StatusBadge status={color} />
                  {locatable && (
                    <MapPin
                      className="size-3.5 text-muted-foreground"
                      aria-hidden="true"
                    />
                  )}
                </div>
                <p className="break-words text-base text-foreground">
                  {field.found ?? <span className="text-muted-foreground">Not found</span>}
                </p>
                {field.reason && (
                  <p className="text-xs text-muted-foreground">{field.reason}</p>
                )}
              </div>
            </div>
          );

          return (
            <li key={field.field}>
              {locatable && onSelect ? (
                <button
                  type="button"
                  onClick={() => onSelect(field.field)}
                  aria-pressed={isActive}
                  className="block w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  {content}
                </button>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
