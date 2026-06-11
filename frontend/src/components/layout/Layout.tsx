import { Outlet } from "react-router-dom";

import { Footer } from "./Footer";
import { GovBanner } from "./GovBanner";
import { Header } from "./Header";

/**
 * App shell: government banner, header, the routed page content, and footer.
 * The main region grows to fill the viewport so the footer stays at the bottom.
 *
 * A skip link is the first focusable element so keyboard and screen-reader
 * users can jump past the banner and nav straight to the page content
 * (WCAG 2.4.1 / Section 508). It is visually hidden until focused.
 */
export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        Skip to main content
      </a>
      <GovBanner />
      <Header />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1480px] flex-1 px-7 py-6 focus:outline-none"
      >
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
