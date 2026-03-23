import { useState } from "react";
import type { Page } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// usePageState — simple client-side navigation state
//
// In production this would be replaced by React Router DOM's useNavigate/
// useLocation hooks. This lightweight version is intentionally framework-
// agnostic so the feature code stays unaware of the routing mechanism.
// ─────────────────────────────────────────────────────────────────────────────

interface PageState {
  page:       Page;
  setPage:    (p: Page) => void;
  loggedIn:   boolean;
  setLoggedIn:(v: boolean) => void;
}

const detectInitialPage = (fallback: Page): Page => {
  const { pathname, search } = window.location;
  const params = new URLSearchParams(search);
  // Erkennt /reset-password?token=... (mit oder ohne Pfad, für SPA-Fallback-Szenarien)
  if (pathname.includes("reset-password") || params.has("token")) return "reset-password";
  return fallback;
};

export const usePageState = (initialPage: Page = "landing"): PageState => {
  const [page, setPage]         = useState<Page>(() => detectInitialPage(initialPage));
  const [loggedIn, setLoggedIn] = useState(false);
  return { page, setPage, loggedIn, setLoggedIn };
};
