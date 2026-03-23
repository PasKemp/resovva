import { useState, useEffect } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import { authApi } from "../../services/api";
import type { Page, WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// ResetPassword — Seite für den Passwort-Reset via E-Mail-Link
//
// Aufgerufen via /reset-password?token=<raw-token>
// Token wird aus window.location.search gelesen.
// ─────────────────────────────────────────────────────────────────────────────

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
  color:        "#D9534F",
  fontFamily:   typography.sans,
  padding:      "10px 14px",
  background:   "#FDF2F2",
  borderRadius: 8,
  border:       "1px solid #F5C6C5",
};

const SUCCESS_STYLE: React.CSSProperties = {
  ...ERROR_STYLE,
  color:      colors.teal,
  background: colors.tealLight,
  border:     `1px solid ${colors.teal}`,
};

type ResetState = "form" | "success" | "invalid-token";

interface ResetPasswordProps extends WithSetPage {}

export const ResetPassword = ({ setPage }: ResetPasswordProps) => {
  const [token,           setToken]           = useState<string | null>(null);
  const [password,        setPassword]        = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [state,           setState]           = useState<ResetState>("form");

  // Token aus URL lesen
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("token");
    if (!raw) {
      setState("invalid-token");
    } else {
      setToken(raw);
    }
  }, []);

  const handleSubmit = async () => {
    setError(null);

    if (!password || !passwordConfirm) {
      setError("Bitte beide Passwortfelder ausfüllen.");
      return;
    }
    if (password.length < 8) {
      setError("Passwort muss mindestens 8 Zeichen lang sein.");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Passwörter stimmen nicht überein.");
      return;
    }
    if (!token) {
      setState("invalid-token");
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setState("success");
    } catch (err: any) {
      const msg = err?.message ?? "";
      if (msg.includes("400") || msg.includes("invalid") || msg.includes("expired")) {
        setError("Der Reset-Link ist ungültig oder abgelaufen. Bitte fordere einen neuen an.");
      } else {
        setError("Etwas ist schiefgelaufen. Bitte versuche es erneut.");
      }
    } finally {
      setLoading(false);
    }
  };

  const goToLogin = () => setPage("login" as Page);

  // ── Render ─────────────────────────────────────────────────────────────────

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

        {/* Ungültiger Token */}
        {state === "invalid-token" && (
          <>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <Icon name="shield" size={40} color={colors.muted} />
            </div>
            <h2 style={{ ...textStyles.h2, textAlign: "center", marginBottom: 12, fontSize: 22 }}>
              Link ungültig
            </h2>
            <p style={{ ...textStyles.body, textAlign: "center", marginBottom: 28 }}>
              Dieser Reset-Link ist ungültig oder bereits abgelaufen (max. 15 Minuten).
              Bitte fordere einen neuen Link an.
            </p>
            <Button onClick={goToLogin} size="lg" style={{ width: "100%", justifyContent: "center" }}>
              Zum Login
            </Button>
          </>
        )}

        {/* Erfolg */}
        {state === "success" && (
          <>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <Icon name="check" size={40} color={colors.teal} />
            </div>
            <h2 style={{ ...textStyles.h2, textAlign: "center", marginBottom: 12, fontSize: 22 }}>
              Passwort gesetzt
            </h2>
            <div style={{ ...SUCCESS_STYLE, textAlign: "center", marginBottom: 28 }}>
              Dein Passwort wurde erfolgreich geändert. Du kannst dich jetzt anmelden.
            </div>
            <Button onClick={goToLogin} size="lg" style={{ width: "100%", justifyContent: "center" }}>
              Jetzt anmelden
            </Button>
          </>
        )}

        {/* Formular */}
        {state === "form" && (
          <>
            <h2 style={{ ...textStyles.h2, textAlign: "center", marginBottom: 8, fontSize: 24 }}>
              Neues Passwort
            </h2>
            <p style={{ ...textStyles.body, textAlign: "center", marginBottom: 28, color: colors.muted }}>
              Bitte wähle ein neues Passwort (mindestens 8 Zeichen).
            </p>

            {error && <div style={{ ...ERROR_STYLE, marginBottom: 16 }}>{error}</div>}

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <input
                type="password"
                placeholder="Neues Passwort"
                value={password}
                onChange={e => setPassword(e.target.value)}
                style={INPUT_STYLE}
                autoFocus
              />
              <input
                type="password"
                placeholder="Passwort bestätigen"
                value={passwordConfirm}
                onChange={e => setPasswordConfirm(e.target.value)}
                style={INPUT_STYLE}
              />

              <Button
                onClick={handleSubmit}
                disabled={loading}
                size="lg"
                style={{ width: "100%", justifyContent: "center" }}
              >
                {loading
                  ? <span className="spin" style={{ fontSize: 16 }}>⟳</span>
                  : "Passwort speichern"}
              </Button>
            </div>

            <p style={{ ...textStyles.small, textAlign: "center", marginTop: 18 }}>
              <span
                onClick={goToLogin}
                style={{ color: colors.orange, fontWeight: 600, cursor: "pointer" }}
              >
                ← Zurück zum Login
              </span>
            </p>

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
          </>
        )}
      </div>
    </div>
  );
};
