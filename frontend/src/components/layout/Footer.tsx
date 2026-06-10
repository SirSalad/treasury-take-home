/** Minimal footer with prototype provenance. */
export function Footer() {
  return (
    <footer className="border-t bg-secondary text-secondary-foreground">
      <div className="container py-4 text-xs text-muted-foreground">
        <p>
          TTB Label Verification — prototype. Not connected to COLA. For evaluation use only; no
          sensitive data is stored.
        </p>
      </div>
    </footer>
  );
}
