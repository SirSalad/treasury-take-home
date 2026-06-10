import { CheckCircle2, AlertTriangle, XCircle, Info, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  WARNING_VERDICT_COLOR,
  WARNING_VERDICT_LABEL,
  type GovernmentWarningResult,
} from "@/lib/verification";
import type { VerificationStatus } from "@/lib/status";

const ICONS: Record<VerificationStatus, typeof CheckCircle2> = {
  match: CheckCircle2,
  warning: AlertTriangle,
  mismatch: XCircle,
};

const ACCENT: Record<VerificationStatus, string> = {
  match: "border-l-match",
  warning: "border-l-warning",
  mismatch: "border-l-mismatch",
};

interface GovernmentWarningCardProps {
  result: GovernmentWarningResult;
  /** Stable key used when this card's region is selectable on the image. */
  fieldKey?: string;
  active?: boolean;
  onSelect?: (key: string) => void;
}

/**
 * The Government Health Warning result, kept distinct from the field table
 * because it carries its own verdict vocabulary (compliant / altered / missing,
 * per 27 CFR 16.21) and surfaces the specific issues found and the limitations
 * of a text-only check. Selectable when its region was located, like a field row.
 */
export function GovernmentWarningCard({
  result,
  fieldKey = "government_warning",
  active,
  onSelect,
}: GovernmentWarningCardProps) {
  const color = WARNING_VERDICT_COLOR[result.verdict];
  const Icon = ICONS[color];
  const locatable = Boolean(result.box) && Boolean(onSelect);

  const body = (
    <div
      className={cn("space-y-3 border-l-4 p-4 text-left", ACCENT[color], active && "bg-accent/40")}
    >
      <div className="flex items-center gap-2">
        <Icon
          className={cn(
            "size-5 shrink-0",
            color === "match" && "text-match",
            color === "warning" && "text-warning",
            color === "mismatch" && "text-mismatch",
          )}
          aria-hidden="true"
        />
        <h3 className="font-semibold text-foreground">Government Health Warning</h3>
        <Badge variant={color} className="ml-auto">
          {WARNING_VERDICT_LABEL[result.verdict]}
        </Badge>
        {locatable && <MapPin className="size-3.5 text-muted-foreground" aria-hidden="true" />}
      </div>

      {result.found_text && (
        <blockquote className="border-l-2 pl-3 text-sm italic text-muted-foreground">
          {result.found_text}
        </blockquote>
      )}

      {result.issues.length > 0 && (
        <ul className="space-y-1 text-sm text-foreground">
          {result.issues.map((issue, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
              <span>{issue}</span>
            </li>
          ))}
        </ul>
      )}

      {result.limitations.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {result.limitations.map((limitation, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{limitation}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div className="overflow-hidden rounded-lg border">
      {locatable ? (
        <button
          type="button"
          onClick={() => onSelect?.(fieldKey)}
          aria-pressed={active}
          className="block w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          {body}
        </button>
      ) : (
        body
      )}
    </div>
  );
}
