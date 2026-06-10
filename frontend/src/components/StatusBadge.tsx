import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, type VerificationStatus } from "@/lib/status";
import { cn } from "@/lib/utils";

const ICONS: Record<VerificationStatus, typeof CheckCircle2> = {
  match: CheckCircle2,
  warning: AlertTriangle,
  mismatch: XCircle,
};

interface StatusBadgeProps {
  status: VerificationStatus;
  className?: string;
}

/**
 * Color-coded badge for a single verification result. Pairs the status color
 * with an icon and text so meaning never relies on color alone (Section 508).
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const Icon = ICONS[status];
  return (
    <Badge variant={status} className={cn("gap-1", className)}>
      <Icon className="size-3.5" aria-hidden="true" />
      {STATUS_LABEL[status]}
    </Badge>
  );
}
