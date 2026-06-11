import { Link, NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Review Queue", end: true },
  { to: "/verify", label: "New Verification" },
  { to: "/batch", label: "Batch Upload" },
  { to: "/audit", label: "Audit Log" },
];

/**
 * Two-tier federal header (claude-design): agency identity over a navy
 * gradient with the gold accent rule, then a USWDS-blue workspace bar that
 * carries the product name and the primary nav.
 */
export function Header() {
  return (
    <header className="sticky top-0 z-50 shadow-header">
      <div className="border-b-4 border-fed-gold bg-gradient-to-b from-fed-navy-light to-fed-navy">
        <div className="mx-auto max-w-[1480px] px-7 py-[13px]">
          {/* The agency identity is a home link — everyone clicks the logo. */}
          <Link
            to="/"
            aria-label="TTB COLA Label Verification — back to the Review Queue"
            className="flex w-fit items-center gap-[18px] rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fed-gold"
          >
            <div
              aria-hidden="true"
              className="flex h-12 w-12 flex-none items-center justify-center rounded-full"
              style={{
                background: "radial-gradient(circle at 50% 36%, #224d85, #0b1d38)",
                boxShadow:
                  "inset 0 0 0 2px #ffbe2e, inset 0 0 0 4px #162e51, 0 0 0 1px rgba(255,190,46,.35), 0 2px 6px rgba(0,0,0,.35)",
              }}
            >
              <span className="text-[19px] leading-none text-fed-gold [text-shadow:0_1px_2px_rgba(0,0,0,.4)]">
                ★
              </span>
            </div>
            <div className="text-[21px] font-extrabold tracking-[2px] text-white">TTB</div>
            <div className="whitespace-nowrap border-l border-[#2c4d78] pl-4 leading-[1.22]">
              <p className="text-[12.5px] font-bold text-white">
                Alcohol and Tobacco Tax and Trade Bureau
              </p>
              <p className="text-[11px] text-[#9fb6d4]">U.S. Department of the Treasury</p>
            </div>
          </Link>
        </div>
      </div>
      <div className="bg-fed-blue">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-2 px-7 py-[7px]">
          <div className="flex items-center gap-3.5">
            <h1 className="text-[14.5px] font-bold tracking-[.2px] text-white">
              COLA Label Verification
            </h1>
            <span className="whitespace-nowrap rounded-[3px] bg-fed-blue-dark px-[9px] py-[2px] text-xs font-semibold text-[#bcd2ea]">
              Reviewer Workspace
            </span>
          </div>
          <nav aria-label="Primary">
            <ul className="flex items-center gap-1">
              {NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        "rounded px-3 py-1.5 text-[13.5px] font-semibold text-[#dbe4f0] transition-colors hover:text-fed-gold",
                        isActive && "bg-fed-blue-dark text-white",
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
      </div>
    </header>
  );
}
