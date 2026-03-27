import { useState, useRef, useEffect } from "react";
import { colors, textStyles, typography } from "../theme/tokens";
import { Button } from "./Button";
import { Icon } from "./Icon";
import type { Page } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Nav — persistent top navigation bar (US-7.2: größere Toolbar)
// ─────────────────────────────────────────────────────────────────────────────

export interface NavProps {
  page: Page;
  setPage: (p: Page) => void;
  loggedIn: boolean;
  onLogout?: () => void;
}

/** Navigationslinks für nicht eingeloggte Nutzer. */
const PUBLIC_NAV_LINKS = ["Landing", "Preise", "Hilfe"] as const;

/** Navigationslinks für eingeloggte Nutzer. */
const PRIVATE_NAV_LINKS = ["Dashboard", "Hilfe"] as const;

const Logo = ({ onClick }: { onClick: () => void }) => (
  <div
    onClick={onClick}
    style={{ display: "flex", alignItems: "center", cursor: "pointer" }}
    role="link"
    aria-label="Resovva Home"
  >
    <img
      src="/Resovva_Logo_white.png"
      alt="Resovva Logo"
      style={{ height: 50, width: "auto" }}
    />
  </div>
);

const NavPill = ({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    style={{
      background: active ? colors.orangeLight : "transparent",
      border: `1.5px solid ${active ? colors.orange : colors.border}`,
      borderRadius: 50,
      padding: "8px 22px",          // US-7.2: mehr Padding
      fontSize: 14,                  // US-7.2: größer
      fontWeight: 600,
      fontFamily: typography.sans,
      color: active ? colors.orange : colors.mid,
      cursor: "pointer",
      transition: "all .18s",
    }}
  >
    {label}
  </button>
);

// ── Avatar-Dropdown (US-7.4) ─────────────────────────────────────────────────

const AvatarDropdown = ({
  setPage,
  onLogout,
}: {
  setPage: (p: Page) => void;
  onLogout: () => void;
}) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Schließen bei Klick außerhalb
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        onClick={() => setOpen(o => !o)}
        title="Profil"
        style={{
          width: 36,
          height: 36,
          background: colors.orange,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          fontFamily: typography.sans,
          fontSize: 13,
          fontWeight: 700,
          color: "#F5EFE6",
          border: `2px solid ${open ? colors.orangeHover : "transparent"}`,
          transition: "border-color .15s",
        }}
      >
        P
      </div>

      {open && (
        <div style={{
          position: "absolute",
          right: 0,
          top: "calc(100% + 8px)",
          background: colors.white,
          border: `1px solid ${colors.border}`,
          borderRadius: 12,
          boxShadow: "0 8px 32px rgba(0,0,0,.12)",
          minWidth: 180,
          zIndex: 500,
          overflow: "hidden",
        }}>
          <button
            onClick={() => { setOpen(false); setPage("profile"); }}
            style={{
              width: "100%",
              padding: "12px 16px",
              background: "none",
              border: "none",
              textAlign: "left",
              fontFamily: typography.sans,
              fontSize: 14,
              fontWeight: 500,
              color: colors.dark,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 10,
              transition: "background .15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = colors.bg)}
            onMouseLeave={e => (e.currentTarget.style.background = "none")}
          >
            <Icon name="users" size={15} color={colors.mid} />
            Mein Profil
          </button>
          <div style={{ height: 1, background: colors.border }} />
          <button
            onClick={() => { setOpen(false); onLogout(); }}
            style={{
              width: "100%",
              padding: "12px 16px",
              background: "none",
              border: "none",
              textAlign: "left",
              fontFamily: typography.sans,
              fontSize: 14,
              fontWeight: 500,
              color: colors.danger,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 10,
              transition: "background .15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = colors.dangerLight)}
            onMouseLeave={e => (e.currentTarget.style.background = "none")}
          >
            <Icon name="x" size={15} color={colors.danger} />
            Abmelden
          </button>
        </div>
      )}
    </div>
  );
};

// ── Nav ──────────────────────────────────────────────────────────────────────

export const Nav = ({ page, setPage, loggedIn, onLogout }: NavProps) => {
  const handleLogout = onLogout ?? (() => setPage("landing"));

  return (
    <nav style={{
      background: colors.white,
      borderBottom: `1px solid ${colors.border}`,
      padding: "0 40px",
      height: 64,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 200,
    }}>
      {/* Left: logo + nav links */}
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        <Logo onClick={() => setPage("landing")} />

        {!loggedIn && (
          <div style={{ display: "flex", gap: 8 }}>
            {PUBLIC_NAV_LINKS.map(label => (
              <NavPill
                key={label}
                label={label}
                active={page === label.toLowerCase()}
                onClick={() => setPage(label.toLowerCase() as Page)}
              />
            ))}
          </div>
        )}

        {loggedIn && (
          <div style={{ display: "flex", gap: 8 }}>
            {PRIVATE_NAV_LINKS.map(label => (
              <NavPill
                key={label}
                label={label}
                active={page === label.toLowerCase()}
                onClick={() => setPage(label.toLowerCase() as Page)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right: actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {!loggedIn && (
          <>
            <div style={{
              background: colors.bg,
              border: `1px solid ${colors.border}`,
              borderRadius: 50,
              padding: "8px 20px",     // US-7.2: größeres Padding
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: 224,
            }}>
              <Icon name="search" size={14} color={colors.muted} />
              <span style={{ ...textStyles.small, color: colors.muted }}>Fälle durchsuchen</span>
            </div>
            <Button onClick={() => setPage("case")} size="md">
              Jetzt Fall kostenlos prüfen
            </Button>
            <Button onClick={() => setPage("login")} variant="outline" size="md">
              Login
            </Button>
          </>
        )}

        {loggedIn && (
          <AvatarDropdown setPage={setPage} onLogout={handleLogout} />
        )}
      </div>
    </nav>
  );
};
