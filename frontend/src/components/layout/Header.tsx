import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Verify a label", end: true },
  { to: "/batch", label: "Batch upload" },
];

/**
 * Primary site header: agency identity on the left, primary nav on the right.
 * Uses the USWDS primary blue so the federal brand reads immediately.
 */
export function Header() {
  return (
    <header className="bg-primary text-primary-foreground">
      <div className="container flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide opacity-90">
            Alcohol and Tobacco Tax and Trade Bureau
          </p>
          <h1 className="text-xl font-bold leading-tight">Label Verification</h1>
        </div>
        <nav aria-label="Primary">
          <ul className="flex gap-1">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-2 text-sm font-semibold transition-colors hover:bg-white/10",
                      isActive && "bg-white/15 underline underline-offset-4",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
