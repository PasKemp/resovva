import { useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import { profileApi } from "../../services/api";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// CompleteProfile — US-7.3: Bestehende Nutzer ohne Profildaten
//
// Wird angezeigt wenn /auth/me profile_complete=false zurückgibt.
// Nach Ausfüllen → Weiterleitung zum Dashboard.
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
  boxSizing:    "border-box",
};

export const CompleteProfile = ({ setPage }: WithSetPage) => {
  const [firstName,  setFirstName]  = useState("");
  const [lastName,   setLastName]   = useState("");
  const [street,     setStreet]     = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [city,       setCity]       = useState("");
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    if (!firstName || !lastName) { setError("Bitte Vor- und Nachname angeben."); return; }
    if (!street) { setError("Bitte Straße und Hausnummer angeben."); return; }
    if (!/^\d{5}$/.test(postalCode)) { setError("PLZ muss genau 5 Ziffern haben."); return; }
    if (!city) { setError("Bitte Stadt angeben."); return; }

    setLoading(true);
    try {
      await profileApi.update({ first_name: firstName, last_name: lastName, street, postal_code: postalCode, city });
      setPage("dashboard");
    } catch {
      setError("Speichern fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight:      "100vh",
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
        width:        480,
        maxWidth:     "100%",
        boxShadow:    "0 16px 64px rgba(0,0,0,.08)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <div style={{
            width: 42, height: 42, background: colors.orangeLight,
            borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Icon name="users" size={20} color={colors.orange} />
          </div>
          <div>
            <h2 style={{ ...textStyles.h3, fontSize: 20 }}>Profil vervollständigen</h2>
            <p style={{ ...textStyles.small, marginTop: 2 }}>
              Für das rechtssichere Dossier benötigt
            </p>
          </div>
        </div>

        {error && (
          <div style={{
            padding: "10px 14px", background: colors.dangerLight,
            border: `1px solid ${colors.dangerBorder}`, borderRadius: 8,
            color: colors.danger, fontSize: 13, fontFamily: typography.sans, marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <input type="text" placeholder="Vorname" value={firstName}
              onChange={e => setFirstName(e.target.value)} style={INPUT_STYLE} />
            <input type="text" placeholder="Nachname" value={lastName}
              onChange={e => setLastName(e.target.value)} style={INPUT_STYLE} />
          </div>
          <input type="text" placeholder="Straße und Hausnummer" value={street}
            onChange={e => setStreet(e.target.value)} style={INPUT_STYLE} />
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10 }}>
            <input type="text" placeholder="PLZ" value={postalCode} maxLength={5}
              onChange={e => setPostalCode(e.target.value.replace(/\D/g, ""))} style={INPUT_STYLE} />
            <input type="text" placeholder="Stadt" value={city}
              onChange={e => setCity(e.target.value)} style={INPUT_STYLE} />
          </div>

          <Button onClick={handleSubmit} disabled={loading} size="lg" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>
            {loading ? "Speichert…" : "Profil speichern & weiter"}
          </Button>
        </div>
      </div>
    </div>
  );
};
