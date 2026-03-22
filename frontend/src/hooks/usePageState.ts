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

export const usePageState = (initialPage: Page = "landing"): PageState => {
  const [page, setPage]         = useState<Page>(initialPage);
  const [loggedIn, setLoggedIn] = useState(false);
  return { page, setPage, loggedIn, setLoggedIn };
};
