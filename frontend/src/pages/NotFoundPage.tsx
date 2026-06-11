import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold tracking-tight">Page not found</h2>
      <p className="text-muted-foreground">The page you&apos;re looking for doesn&apos;t exist.</p>
      <Button asChild>
        <Link to="/">Back to the Review Queue</Link>
      </Button>
    </div>
  );
}
