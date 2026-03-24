import { colors, textStyles, typography } from "../theme/tokens";
import { Button } from "./Button";
import { Icon } from "./Icon";
import type { Page } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Nav — persistent top navigation bar
// ─────────────────────────────────────────────────────────────────────────────

interface NavProps {
  page: Page;
  setPage: (p: Page) => void;
  loggedIn: boolean;
}

const Logo = ({ onClick }: { onClick: () => void }) => (
  <div
    onClick={onClick}
    style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer" }}
    role="link"
    aria-label="Resovva Home"
  >
    <div style={{
      width: 30, height: 30,
      background: colors.orange,
      borderRadius: 7,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <Icon name="scale" size={15} color="#fff" />
    </div>
    <span style={{ fontFamily: "'DM Serif Display', Georgia, serif", fontSize: 21, color: colors.dark, letterSpacing: "-0.01em" }}>
      Resovva
    </span>
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
      padding: "5px 17px",
      fontSize: 13,
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

export const Nav = ({ page, setPage, loggedIn }: NavProps) => (
  <nav style={{
    background: colors.white,
    borderBottom: `1px solid ${colors.border}`,
    padding: "0 32px",
    height: 60,
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
          {(["Landing", "Preise", "Hilfe"] as const).map(label => (
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
          {(["Dashboard", "Hilfe"] as const).map(label => (
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
            background: "#F5EFE6",
            border: `1px solid ${colors.border}`,
            borderRadius: 50,
            padding: "7px 18px",
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
        <>
          <Button onClick={() => setPage("case")} size="md">
            <Icon name="plus" size={14} color="#fff" />
            Neuer Fall
          </Button>
          {/* Avatar */}
          <div
            title="Profil"
            style={{
              width: 34, height: 34,
              background: colors.orange,
              borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer",
              fontFamily: typography.sans,
              fontSize: 13,
              fontWeight: 700,
              color: "#F5EFE6",
            }}
          >
            AM
          </div>
        </>
      )}
    </div>
  </nav>
);
