import { useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import { authApi } from "../../services/api";
import type { Page, WithSetPage, WithSetLoggedIn } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Login / Register Page (US-7.3: Registrierung um Profilfelder erweitert)
// ─────────────────────────────────────────────────────────────────────────────

type AuthTab = "login" | "register" | "forgot";

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
  boxSizing:    "border-box",
};

const ERROR_STYLE: React.CSSProperties = {
  fontSize:     13,
  color:        colors.danger,
  fontFamily:   typography.sans,
  padding:      "10px 14px",
  background:   colors.dangerLight,
  borderRadius: 8,
  border:       `1px solid ${colors.dangerBorder}`,
};

// ── Sub-components ─────────────────────────────────────────────────────────

const TabSwitcher = ({
  active, onChange,
}: { active: "login" | "register"; onChange: (t: "login" | "register") => void }) => (
  <div style={{
    display:    "flex",
    background: colors.bg,
    borderRadius: 50,
    padding:    4,
    gap:        4,
    width:      "fit-content",
    margin:     "0 auto 28px",
  }}>
    {(["login", "register"] as const).map(tab => (
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
  const [tab,             setTab]             = useState<AuthTab>("login");
  const [email,           setEmail]           = useState("");
  const [password,        setPassword]        = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [accepted,        setAccepted]        = useState(false);
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [successMsg,      setSuccessMsg]      = useState<string | null>(null);

  // Profil-Felder (US-7.3)
  const [firstName,   setFirstName]   = useState("");
  const [lastName,    setLastName]    = useState("");
  const [street,      setStreet]      = useState("");
  const [postalCode,  setPostalCode]  = useState("");
  const [city,        setCity]        = useState("");

  const resetForm = () => {
    setError(null);
    setSuccessMsg(null);
  };

  const handleLogin = async () => {
    resetForm();
    if (!email || !password) { setError("Bitte E-Mail und Passwort eingeben."); return; }
    setLoading(true);
    try {
      await authApi.login({ email, password });
      // Nach erfolgreichem Login Profil-Status abfragen (US-7.3)
      const me = await authApi.me();
      setLoggedIn(true);
      if (!me.profile_complete) {
        setPage("complete-profile" as Page);
      } else {
        setPage("dashboard" as Page);
      }
    } catch {
      setError("E-Mail oder Passwort falsch.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    resetForm();
    if (!email || !password) { setError("Bitte E-Mail und Passwort eingeben."); return; }
    if (password.length < 8) { setError("Passwort muss mindestens 8 Zeichen lang sein."); return; }
    if (password !== passwordConfirm) { setError("Passwörter stimmen nicht überein."); return; }
    if (!accepted) { setError("Bitte AGB und Datenschutzerklärung akzeptieren."); return; }
    if (!firstName || !lastName) { setError("Bitte Vor- und Nachname angeben."); return; }
    if (!street) { setError("Bitte Straße und Hausnummer angeben."); return; }
    if (!/^\d{5}$/.test(postalCode)) { setError("PLZ muss genau 5 Ziffern haben."); return; }
    if (!city) { setError("Bitte Stadt angeben."); return; }

    setLoading(true);
    try {
      await authApi.register({
        email,
        password,
        accepted_terms: true,
        first_name: firstName,
        last_name:  lastName,
        street,
        postal_code: postalCode,
        city,
      });
      setLoggedIn(true);
      setPage("dashboard" as Page);
    } catch (err: any) {
      const msg = err?.message ?? "";
      if (msg.includes("409") || msg.includes("bereits verwendet")) {
        setError("Diese E-Mail-Adresse wird bereits verwendet.");
      } else if (msg.includes("422")) {
        setError("Bitte alle Felder korrekt ausfüllen.");
      } else {
        setError("Registrierung fehlgeschlagen. Bitte erneut versuchen.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    resetForm();
    if (!email) { setError("Bitte E-Mail-Adresse eingeben."); return; }
    setLoading(true);
    try {
      const res = await authApi.forgotPassword(email);
      setSuccessMsg(res.message);
    } catch {
      setSuccessMsg("Falls ein Account existiert, wurde eine E-Mail gesendet.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (tab === "login")    return handleLogin();
    if (tab === "register") return handleRegister();
    if (tab === "forgot")   return handleForgotPassword();
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  // Breite je nach Tab: Register braucht mehr Platz für die 2-spaltige Adresse
  const cardWidth = tab === "register" ? 520 : 420;

  return (
    <div style={{
      minHeight:      "calc(100vh - 64px)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      background:     `linear-gradient(135deg, ${colors.bg} 0%, #EEF0FA 100%)`,
      padding:        "32px 16px",
    }}>
      <div className="fade-up" style={{
        background:   colors.white,
        borderRadius: 16,
        border:       `1px solid ${colors.border}`,
        padding:      "40px 36px",
        width:        cardWidth,
        maxWidth:     "100%",
        boxShadow:    "0 16px 64px rgba(0,0,0,.08)",
      }}>

        {tab !== "forgot" && (
          <TabSwitcher
            active={tab as "login" | "register"}
            onChange={(t) => { setTab(t); resetForm(); }}
          />
        )}

        <h2 style={{ ...textStyles.h2, textAlign: "center", marginBottom: 28, fontSize: 24 }}>
          {tab === "login"    && "Anmelden"}
          {tab === "register" && "Konto erstellen"}
          {tab === "forgot"   && "Passwort vergessen"}
        </h2>

        {error      && <div style={{ ...ERROR_STYLE, marginBottom: 16 }}>{error}</div>}
        {successMsg && (
          <div style={{ ...ERROR_STYLE, color: colors.teal, background: colors.tealLight, border: `1px solid ${colors.teal}`, marginBottom: 16 }}>
            {successMsg}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <input
            type="email"
            placeholder="E-Mail"
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={INPUT_STYLE}
          />

          {tab !== "forgot" && (
            <input
              type="password"
              placeholder="Passwort"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={INPUT_STYLE}
            />
          )}

          {tab === "register" && (
            <input
              type="password"
              placeholder="Passwort bestätigen"
              value={passwordConfirm}
              onChange={e => setPasswordConfirm(e.target.value)}
              style={INPUT_STYLE}
            />
          )}

          {/* ── Profil-Felder (US-7.3) – nur bei Registrierung ──────────── */}
          {tab === "register" && (
            <>
              <div style={{ height: 1, background: colors.border, margin: "4px 0" }} />
              <p style={{ ...textStyles.label, color: colors.muted }}>Persönliche Daten</p>

              {/* Vor- / Nachname — 2-spaltig */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <input
                  type="text"
                  placeholder="Vorname"
                  value={firstName}
                  onChange={e => setFirstName(e.target.value)}
                  style={INPUT_STYLE}
                />
                <input
                  type="text"
                  placeholder="Nachname"
                  value={lastName}
                  onChange={e => setLastName(e.target.value)}
                  style={INPUT_STYLE}
                />
              </div>

              {/* Straße + Hausnummer */}
              <input
                type="text"
                placeholder="Straße und Hausnummer"
                value={street}
                onChange={e => setStreet(e.target.value)}
                style={INPUT_STYLE}
              />

              {/* PLZ (schmal) + Stadt (breit) — 2-spaltig */}
              <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10 }}>
                <input
                  type="text"
                  placeholder="PLZ"
                  value={postalCode}
                  maxLength={5}
                  onChange={e => setPostalCode(e.target.value.replace(/\D/g, ""))}
                  style={INPUT_STYLE}
                />
                <input
                  type="text"
                  placeholder="Stadt"
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  style={INPUT_STYLE}
                />
              </div>
            </>
          )}

          {tab === "register" && (
            <>
              <div style={{ height: 1, background: colors.border, margin: "4px 0" }} />
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
            </>
          )}

          <Button
            onClick={handleSubmit}
            disabled={loading || (tab === "register" && !accepted)}
            size="lg"
            style={{ width: "100%", justifyContent: "center" }}
          >
            {loading
              ? <span className="spin" style={{ fontSize: 16 }}>⟳</span>
              : tab === "login"    ? "Anmelden"
              : tab === "register" ? "Registrieren"
              : "Reset-Link senden"}
          </Button>
        </div>

        {tab === "login" && (
          <div style={{ marginTop: 18, textAlign: "center" }}>
            <p style={{ ...textStyles.small, color: colors.muted, marginBottom: 8 }}>
              Noch kein Konto?{" "}
              <span
                onClick={() => { setTab("register"); resetForm(); }}
                style={{ color: colors.orange, fontWeight: 600, cursor: "pointer" }}
              >
                Jetzt registrieren
              </span>
            </p>
            <span
              onClick={() => { setTab("forgot"); resetForm(); }}
              style={{ ...textStyles.small, color: colors.muted, cursor: "pointer", textDecoration: "underline" }}
            >
              Passwort vergessen?
            </span>
          </div>
        )}

        {(tab === "register" || tab === "forgot") && (
          <p style={{ ...textStyles.small, textAlign: "center", marginTop: 18, color: colors.muted }}>
            <span
              onClick={() => { setTab("login"); resetForm(); }}
              style={{ color: colors.orange, fontWeight: 600, cursor: "pointer" }}
            >
              ← Zurück zum Login
            </span>
          </p>
        )}

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
