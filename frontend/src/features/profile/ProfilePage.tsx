import { useEffect, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Card, Icon } from "../../components";
import { authApi, profileApi } from "../../services/api";
import type { MeResponse } from "../../services/api";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// ProfilePage — US-7.4: Profilseite – Daten ändern & Account löschen
// ─────────────────────────────────────────────────────────────────────────────

const INPUT_STYLE: React.CSSProperties = {
  width:        "100%",
  padding:      "11px 14px",
  border:       `1.5px solid ${colors.border}`,
  borderRadius: 9,
  fontSize:     14,
  fontFamily:   typography.sans,
  color:        colors.dark,
  outline:      "none",
  background:   colors.bg,
  boxSizing:    "border-box",
};

const SectionCard = ({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) => (
  <Card style={{ marginBottom: 20 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${colors.border}` }}>
      <div style={{
        width: 36, height: 36, background: colors.orangeLight,
        borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon name={icon as any} size={17} color={colors.orange} />
      </div>
      <h3 style={{ ...textStyles.h3, fontSize: 16 }}>{title}</h3>
    </div>
    {children}
  </Card>
);

// ── Delete-Modal ──────────────────────────────────────────────────────────────

const DeleteAccountModal = ({
  email, onConfirm, onCancel, loading,
}: { email: string; onConfirm: () => void; onCancel: () => void; loading: boolean }) => {
  const [typed, setTyped] = useState("");
  return (
    <div style={{
      position: "fixed", inset: 0,
      background: "rgba(0,0,0,.5)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: colors.white, borderRadius: 16, padding: "36px 32px",
        maxWidth: 460, width: "90%", boxShadow: "0 24px 80px rgba(0,0,0,.2)",
      }}>
        <h3 style={{ ...textStyles.h3, color: colors.danger, marginBottom: 12 }}>
          Account unwiderruflich löschen?
        </h3>
        <p style={{ ...textStyles.body, color: colors.mid, marginBottom: 20 }}>
          Alle deine Fälle, Dokumente und Analysen werden dauerhaft gelöscht.
          Diese Aktion kann nicht rückgängig gemacht werden.
        </p>
        <p style={{ ...textStyles.small, marginBottom: 8 }}>
          Zur Bestätigung bitte E-Mail-Adresse eingeben:
        </p>
        <input
          type="email"
          placeholder={email}
          value={typed}
          onChange={e => setTyped(e.target.value)}
          style={{ ...INPUT_STYLE, marginBottom: 20 }}
        />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <Button variant="outline" size="md" onClick={onCancel} disabled={loading}>Abbrechen</Button>
          <Button
            size="md" disabled={loading || typed !== email}
            onClick={onConfirm}
            style={{ background: colors.danger, color: "#fff" }}
          >
            {loading ? "Wird gelöscht…" : "Account löschen"}
          </Button>
        </div>
      </div>
    </div>
  );
};

// ── ProfilePage ───────────────────────────────────────────────────────────────

export const ProfilePage = ({ setPage }: WithSetPage) => {
  const [user,         setUser]         = useState<MeResponse | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [saveMsg,      setSaveMsg]      = useState<string | null>(null);
  const [saveError,    setSaveError]    = useState<string | null>(null);
  const [showDelete,   setShowDelete]   = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Profil-Felder
  const [firstName,   setFirstName]   = useState("");
  const [lastName,    setLastName]    = useState("");
  const [street,      setStreet]      = useState("");
  const [postalCode,  setPostalCode]  = useState("");
  const [city,        setCity]        = useState("");

  // Passwort
  const [oldPw,   setOldPw]   = useState("");
  const [newPw,   setNewPw]   = useState("");
  const [pwMsg,   setPwMsg]   = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwLoading, setPwLoading] = useState(false);

  useEffect(() => {
    authApi.me()
      .then(u => {
        setUser(u);
        setFirstName(u.first_name  ?? "");
        setLastName(u.last_name    ?? "");
        setStreet(u.street         ?? "");
        setPostalCode(u.postal_code ?? "");
        setCity(u.city             ?? "");
      })
      .catch(() => setPage("login"))
      .finally(() => setLoading(false));
  }, []);

  const handleSaveProfile = async () => {
    setSaveMsg(null); setSaveError(null);
    if (!firstName || !lastName) { setSaveError("Vor- und Nachname erforderlich."); return; }
    if (!/^\d{5}$/.test(postalCode)) { setSaveError("PLZ muss genau 5 Ziffern haben."); return; }
    if (!street || !city) { setSaveError("Bitte Adresse vollständig angeben."); return; }
    try {
      await profileApi.update({ first_name: firstName, last_name: lastName, street, postal_code: postalCode, city });
      setSaveMsg("Profil erfolgreich gespeichert.");
    } catch {
      setSaveError("Speichern fehlgeschlagen.");
    }
  };

  const handleChangePassword = async () => {
    setPwMsg(null); setPwError(null);
    if (!oldPw || !newPw) { setPwError("Bitte beide Felder ausfüllen."); return; }
    if (newPw.length < 8) { setPwError("Neues Passwort muss min. 8 Zeichen haben."); return; }
    setPwLoading(true);
    try {
      await profileApi.changePassword(oldPw, newPw);
      setPwMsg("Passwort erfolgreich geändert.");
      setOldPw(""); setNewPw("");
    } catch {
      setPwError("Aktuelles Passwort ist falsch.");
    } finally {
      setPwLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleteLoading(true);
    try {
      await profileApi.deleteAccount();
      setPage("landing");
    } catch {
      setDeleteLoading(false);
      setShowDelete(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <p style={{ ...textStyles.body, color: colors.muted }}>Lädt…</p>
      </div>
    );
  }

  return (
    <>
      {showDelete && user && (
        <DeleteAccountModal
          email={user.email}
          onConfirm={handleDeleteAccount}
          onCancel={() => setShowDelete(false)}
          loading={deleteLoading}
        />
      )}

      <div style={{ maxWidth: 680, margin: "0 auto", padding: "32px 24px 64px" }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={() => setPage("dashboard")}
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontFamily: typography.sans, fontSize: 13,
              color: colors.muted, marginBottom: 12, display: "flex", alignItems: "center", gap: 6,
            }}
          >
            <Icon name="arrow" size={12} color={colors.muted} style={{ transform: "rotate(180deg)" }} />
            Zurück zum Dashboard
          </button>
          <h1 style={{ ...textStyles.h2, fontSize: 26 }}>Mein Profil</h1>
          <p style={{ ...textStyles.body, color: colors.muted }}>{user?.email}</p>
        </div>

        {/* ── Persönliche Daten ── */}
        <SectionCard title="Persönliche Daten" icon="users">
          {saveMsg   && <p style={{ color: colors.greenText, fontSize: 13, fontFamily: typography.sans, marginBottom: 14 }}>✓ {saveMsg}</p>}
          {saveError && <p style={{ color: colors.danger,    fontSize: 13, fontFamily: typography.sans, marginBottom: 14 }}>✕ {saveError}</p>}

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Vorname</label>
                <input type="text" value={firstName} onChange={e => setFirstName(e.target.value)} style={INPUT_STYLE} />
              </div>
              <div>
                <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Nachname</label>
                <input type="text" value={lastName} onChange={e => setLastName(e.target.value)} style={INPUT_STYLE} />
              </div>
            </div>
            <div>
              <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Straße und Hausnummer</label>
              <input type="text" value={street} onChange={e => setStreet(e.target.value)} style={INPUT_STYLE} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10 }}>
              <div>
                <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>PLZ</label>
                <input type="text" value={postalCode} maxLength={5}
                  onChange={e => setPostalCode(e.target.value.replace(/\D/g, ""))} style={INPUT_STYLE} />
              </div>
              <div>
                <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Stadt</label>
                <input type="text" value={city} onChange={e => setCity(e.target.value)} style={INPUT_STYLE} />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
              <Button size="md" onClick={handleSaveProfile}>Änderungen speichern</Button>
            </div>
          </div>
        </SectionCard>

        {/* ── Login-Daten ── */}
        <SectionCard title="Passwort ändern" icon="shield">
          {pwMsg   && <p style={{ color: colors.greenText, fontSize: 13, fontFamily: typography.sans, marginBottom: 14 }}>✓ {pwMsg}</p>}
          {pwError && <p style={{ color: colors.danger,    fontSize: 13, fontFamily: typography.sans, marginBottom: 14 }}>✕ {pwError}</p>}

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Aktuelles Passwort</label>
              <input type="password" value={oldPw} onChange={e => setOldPw(e.target.value)} style={INPUT_STYLE} />
            </div>
            <div>
              <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Neues Passwort</label>
              <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} style={INPUT_STYLE} />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
              <Button size="md" onClick={handleChangePassword} disabled={pwLoading}>
                {pwLoading ? "Speichert…" : "Passwort ändern"}
              </Button>
            </div>
          </div>
        </SectionCard>

        {/* ── Account löschen ── */}
        <Card style={{ border: `1px solid ${colors.dangerBorder}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, paddingBottom: 14, borderBottom: `1px solid ${colors.dangerBorder}` }}>
            <div style={{
              width: 36, height: 36, background: colors.dangerLight,
              borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name="x" size={17} color={colors.danger} />
            </div>
            <h3 style={{ ...textStyles.h3, fontSize: 16, color: colors.danger }}>Account löschen</h3>
          </div>
          <p style={{ ...textStyles.body, color: colors.mid, marginBottom: 18 }}>
            Löscht deinen Account und alle zugehörigen Daten dauerhaft (DSGVO-konform).
            Diese Aktion ist unwiderruflich.
          </p>
          <Button
            size="md"
            onClick={() => setShowDelete(true)}
            style={{ background: colors.danger, color: "#fff" }}
          >
            Account unwiderruflich löschen
          </Button>
        </Card>
      </div>
    </>
  );
};
