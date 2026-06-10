import * as React from "react";

import { cn } from "@/lib/utils";

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  /** Renders a required marker (and screen-reader text) after the label. */
  required?: boolean;
}

/** Form label with an accessible required indicator. */
const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, required, children, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn("text-base font-semibold leading-none text-foreground", className)}
        {...props}
      >
        {children}
        {required && (
          <span className="ml-1 text-destructive">
            <span aria-hidden="true">*</span>
            <span className="sr-only">(required)</span>
          </span>
        )}
      </label>
    );
  },
);
Label.displayName = "Label";

export { Label };
