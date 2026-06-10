import { AlertCircle } from "lucide-react";
import * as React from "react";

import { Label } from "@/components/ui/label";

interface FieldRenderProps {
  /** Wire to the control's `id` so the `<label>` points at it. */
  id: string;
  /** Wire to the control's `aria-describedby` (help + error text). */
  describedBy: string | undefined;
  /** Wire to the control's `aria-invalid`. */
  invalid: boolean;
}

interface FieldProps {
  /** Stable id used to derive the control, help, and error element ids. */
  id: string;
  label: string;
  /** Guidance shown under the label, e.g. an example value. */
  help?: string;
  /** Validation message; presence flips the field into the error state. */
  error?: string;
  required?: boolean;
  /**
   * Render the control. Receives the ids/flags it must spread so the label,
   * help text, and error are programmatically associated (Section 508 / WCAG
   * 1.3.1, 3.3.1).
   */
  children: (props: FieldRenderProps) => React.ReactNode;
}

/**
 * Layout + accessibility wrapper for a single form control. Associates the
 * label, optional help text, and validation error with the input via
 * `htmlFor` / `aria-describedby` / `aria-invalid`, and announces errors with
 * `role="alert"` so screen readers read them when they appear.
 */
export function Field({ id, label, help, error, required, children }: FieldProps) {
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      {help && (
        <p id={helpId} className="text-sm text-muted-foreground">
          {help}
        </p>
      )}
      {children({ id, describedBy, invalid: Boolean(error) })}
      {error && (
        <p
          id={errorId}
          role="alert"
          className="flex items-center gap-1 text-sm font-medium text-destructive"
        >
          <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
