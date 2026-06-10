import { Outlet } from "react-router-dom";

import { Footer } from "./Footer";
import { GovBanner } from "./GovBanner";
import { Header } from "./Header";

/**
 * App shell: government banner, header, the routed page content, and footer.
 * The main region grows to fill the viewport so the footer stays at the bottom.
 */
export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <GovBanner />
      <Header />
      <main className="container flex-1 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
