import { StrictMode } from "react";
import { createRoot }  from "react-dom/client";
import "./index.css";
import App from "./App";

// ─────────────────────────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────────────────────────

const container = document.getElementById("root");

if (!container) {
  throw new Error(
    "Could not find #root element. Make sure index.html has <div id='root'>.</div>",
  );
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
