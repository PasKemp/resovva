import { useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import type { Page, WithSetPage, WithSetLoggedIn } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Login / Register Page
// ─────────────────────────────────────────────────────────────────────────────

type AuthTab = "login" | "register";

const INPUT_STYLE: React.CSSProperties = {
  width:        "100%",
  padding:      "12px 16px",
  border:       `1.5px solid ${colors.border}`,
  borderRadius: 10,
  fontSize:     14,
  fontFamily:   typography.sans,
  color:        colors.dark,
  outline:      "none",
  background:   colors.bg,
  transition:   "border-color .18s",
};

// ── Sub-components ─────────────────────────────────────────────────────────

const TabSwitcher = ({
  active, onChange,
}: { active: AuthTab; onChange: (t: AuthTab) => void }) => (
  <div style={{
    display: "flex",
    background: colors.bg,
    borderRadius: 50,
    padding: 4,
    gap: 4,
    width: "fit-content",
    margin: "0 auto 28px",
  }}>
    {(["login", "register"] as AuthTab[]).map(tab => (
      <button
        key={tab}
        onClick={() => onChange(tab)}
        style={{
          padding:      "8px 28px",
          borderRadius: 50,
          border:       "none",
          fontFamily:   typography.sans,
          fontSize:     13,
          fontWeight:   600,
          cursor:       "pointer",
          background:   active === tab ? colors.white : "transparent",
          color:        active === tab ? colors.dark : colors.muted,
          boxShadow:    active === tab ? "0 2px 8px rgba(0,0,0,.08)" : "none",
          transition:   "all .2s",
        }}
      >
        {tab === "login" ? "Login" : "Registrieren"}
      </button>
    ))}
  </div>
);

// ── Login ──────────────────────────────────────────────────────────────────

interface LoginProps extends WithSetPage, WithSetLoggedIn {}

export const Login = ({ setPage, setLoggedIn }: LoginProps) => {
  const [tab,      setTab]      = useState<AuthTab>("login");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [loading,  setLoading]  = useState(false);

  const handleSubmit = () => {
    if (!accepted) return;
    setLoading(true);
    // Simulated auth — replace with authApi.login() call
    setTimeout(() => {
      setLoading(false);
      setLoggedIn(true);
      setPage("dashboard" as Page);
    }, 1200);
  };

  return (
    <div style={{
      minHeight:      "calc(100vh - 60px)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      background:     `linear-gradient(135deg, ${colors.bg} 0%, #EEF0FA 100%)`,
    }}>
      <div className="fade-up" style={{
        background:   colors.white,
        borderRadius: 16,
        border:       `1px solid ${colors.border}`,
        padding:      "40px 36px",
        width:        420,
        boxShadow:    "0 16px 64px rgba(0,0,0,.08)",
      }}>
        <TabSwitcher active={tab} onChange={setTab} />

        <h2 style={{ ...textStyles.h2, textAlign: "center", marginBottom: 28, fontSize: 24 }}>
          {tab === "login" ? "Login" : "Konto erstellen"}
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {tab === "register" && (
            <input placeholder="Name" style={INPUT_STYLE} />
          )}

          <input
            type="email"
            placeholder="E-Mail"
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={INPUT_STYLE}
          />
          <input
            type="password"
            placeholder="Passwort"
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={INPUT_STYLE}
          />
          {tab === "register" && (
            <input type="password" placeholder="Passwort wiederholen" style={INPUT_STYLE} />
          )}

          <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={accepted}
              onChange={e => setAccepted(e.target.checked)}
              style={{ marginTop: 3, accentColor: colors.orange, width: 15, height: 15, flexShrink: 0 }}
            />
            <span style={{ ...textStyles.small, color: colors.muted, lineHeight: 1.5 }}>
              Ich akzeptiere die{" "}
              <span style={{ color: colors.orange, cursor: "pointer" }}>AGB</span>{" "}
              und die{" "}
              <span style={{ color: colors.orange, cursor: "pointer" }}>Datenschutzerklärung</span>
            </span>
          </label>

          <Button
            onClick={handleSubmit}
            disabled={loading || !accepted}
            size="lg"
            style={{ width: "100%", justifyContent: "center" }}
          >
            {loading
              ? <span className="spin" style={{ fontSize: 16 }}>⟳</span>
              : (tab === "login" ? "Anmelden" : "Registrieren")}
          </Button>
        </div>

        {tab === "login" && (
          <p style={{ ...textStyles.small, textAlign: "center", marginTop: 20, color: colors.muted }}>
            Noch kein Konto?{" "}
            <span
              onClick={() => setTab("register")}
              style={{ color: colors.orange, fontWeight: 600, cursor: "pointer" }}
            >
              Jetzt registrieren
            </span>
          </p>
        )}

        {/* DSGVO notice */}
        <div style={{
          marginTop:    24,
          padding:      "13px 15px",
          background:   colors.tealLight,
          borderRadius: 10,
          display:      "flex",
          gap:          10,
          alignItems:   "flex-start",
        }}>
          <Icon name="shield" size={16} color={colors.teal} style={{ marginTop: 1, flexShrink: 0 }} />
          <p style={{ ...textStyles.small, color: colors.teal, lineHeight: 1.5 }}>
            Ihre Daten sind DSGVO-konform verschlüsselt und werden nicht an Dritte weitergegeben.
          </p>
        </div>
      </div>
    </div>
  );
};
