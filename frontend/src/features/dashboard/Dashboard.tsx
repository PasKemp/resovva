import { useEffect, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Badge, Card, Icon } from "../../components";
import { authApi, casesApi } from "../../services/api";
import { mapApiCase } from "../../types";
import type { Case, CaseStatus, WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<CaseStatus, "orange" | "yellow" | "teal"> = {
  Entwurf:                "orange",
  "Wartet auf Zahlung":   "yellow",
  Abgeschlossen:          "teal",
};

// ── Delete-Confirm-Modal ─────────────────────────────────────────────────────

const DeleteModal = ({
  onConfirm,
  onCancel,
  loading,
}: {
  onConfirm: () => void;
  onCancel:  () => void;
  loading:   boolean;
}) => (
  <div style={{
    position:       "fixed",
    inset:          0,
    background:     "rgba(0,0,0,.45)",
    zIndex:         1000,
    display:        "flex",
    alignItems:     "center",
    justifyContent: "center",
  }}>
    <div style={{
      background:   colors.white,
      borderRadius: 16,
      padding:      "36px 32px",
      maxWidth:     440,
      width:        "90%",
      boxShadow:    "0 24px 80px rgba(0,0,0,.2)",
    }}>
      <h3 style={{ ...textStyles.h3, marginBottom: 12, color: "#D9534F" }}>
        Fall unwiderruflich löschen?
      </h3>
      <p style={{ ...textStyles.body, marginBottom: 28, color: colors.mid }}>
        Diese Aktion kann nicht rückgängig gemacht werden. Alle Dokumente,
        Analysen und die Chronologie werden dauerhaft gelöscht.
      </p>
      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <Button variant="outline" size="md" onClick={onCancel} disabled={loading}>
          Abbrechen
        </Button>
        <Button
          size="md"
          onClick={onConfirm}
          disabled={loading}
          style={{ background: "#D9534F", color: "#fff" }}
        >
          {loading ? "Löschen…" : "Ja, dauerhaft löschen"}
        </Button>
      </div>
    </div>
  </div>
);

// ── Sub-components ─────────────────────────────────────────────────────────

interface SidebarProps extends WithSetPage {
  onLogout: () => void;
  onNewCase: () => void;
}

const Sidebar = ({ onLogout, onNewCase }: SidebarProps) => (
  <div style={{
    width:       224,
    background:  colors.white,
    borderRight: `1px solid ${colors.border}`,
    padding:     22,
    flexShrink:  0,
    display:     "flex",
    flexDirection: "column",
    justifyContent: "space-between",
  }}>
    <div>
      <h3 style={{ ...textStyles.h3, fontSize: 15, marginBottom: 4 }}>Übersicht</h3>
      <p style={{ ...textStyles.small, marginBottom: 20 }}>
        Deine Fälle, Status und Schnellaktionen
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        <Button onClick={onNewCase} size="sm" style={{ justifyContent: "center" }}>
          <Icon name="plus"     size={14} color="#fff" /> Neuen Fall starten
        </Button>
        <Button variant="outline" size="sm" style={{ justifyContent: "center" }}>
          <Icon name="import"   size={14} color={colors.mid} /> Importieren
        </Button>
        <Button variant="outline" size="sm" style={{ justifyContent: "center" }}>
          <Icon name="template" size={14} color={colors.mid} /> Vorlagen
        </Button>
      </div>
    </div>

    {/* Abmelden-Button unten */}
    <Button
      variant="ghost"
      size="sm"
      onClick={onLogout}
      style={{ justifyContent: "center", color: colors.muted }}
    >
      Abmelden
    </Button>
  </div>
);

const WelcomeCard = ({ onNewCase }: { onNewCase: () => void }) => (
  <Card style={{ marginBottom: 24 }}>
    <div style={{
      display:             "grid",
      gridTemplateColumns: "1fr auto",
      gap:                 24,
      alignItems:          "start",
    }}>
      <div>
        <h2 style={{ ...textStyles.h2, fontSize: 21, marginBottom: 8 }}>
          Willkommen bei Resovva. Lass uns deinen ersten Fall lösen.
        </h2>
        <p style={{ ...textStyles.body, marginBottom: 20 }}>
          Keine Sorge – wir führen dich Schritt für Schritt durch den Prozess.
        </p>
        <div style={{ display: "flex", gap: 12 }}>
          <Button onClick={onNewCase} size="md">
            <Icon name="plus" size={14} color="#fff" /> Neuen Fall starten
          </Button>
          <Button variant="outline" size="md">Hilfe ansehen</Button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {([
          { icon: "upload" as const, label: "Dokumente\nhochladen" },
          { icon: "list"   as const, label: "Chronologie\nprüfen" },
          { icon: "folder" as const, label: "Dossier\nerhalten" },
        ] as const).map(({ icon, label }) => (
          <div key={label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 40, height: 40,
              background:   colors.tealLight,
              borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name={icon} size={18} color={colors.teal} />
            </div>
            <span style={{
              fontSize:   11, color: colors.mid,
              textAlign:  "center",
              whiteSpace: "pre",
              lineHeight: 1.4,
              fontFamily: typography.sans,
            }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  </Card>
);

const CaseCard = ({
  c,
  setPage,
  onDelete,
}: {
  c:        Case;
  setPage:  (p: any) => void;
  onDelete: () => void;
}) => {
  const isEditable     = c.status === "Entwurf";
  const isDownloadable = c.status === "Abgeschlossen";

  return (
    <div className="card-hover" style={{
      background:   colors.white,
      border:       `1px solid ${colors.border}`,
      borderRadius: 12,
      padding:      "18px 20px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <p style={{ ...textStyles.label, marginBottom: 2 }}>Fall-ID</p>
          <p style={{ fontFamily: typography.sans, fontSize: 17, fontWeight: 700, color: colors.dark }}>
            {c.id}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ ...textStyles.label, marginBottom: 2 }}>Datum</p>
          <p style={{ ...textStyles.body, fontSize: 13 }}>{c.date}</p>
        </div>
      </div>

      <p style={{ ...textStyles.small, marginBottom: 14 }}>
        Netzbetreiber:{" "}
        <span style={{ fontWeight: 600, color: colors.dark }}>{c.operator}</span>
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Badge color={STATUS_COLOR[c.status]}>{c.status}</Badge>
        <div style={{ display: "flex", gap: 8 }}>
          {isEditable && (
            <Button onClick={() => setPage("case")} variant="outline" size="sm">
              Bearbeiten
            </Button>
          )}
          {isDownloadable && (
            <Button variant="teal" size="sm">
              <Icon name="download" size={13} color="#fff" /> Download
            </Button>
          )}
          {/* Löschen-Button */}
          <button
            onClick={onDelete}
            title="Fall löschen"
            style={{
              background:   "none",
              border:       "none",
              cursor:       "pointer",
              color:        colors.muted,
              padding:      "4px 6px",
              borderRadius: 6,
              transition:   "color .15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.color = "#D9534F")}
            onMouseLeave={e => (e.currentTarget.style.color = colors.muted)}
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Dashboard ──────────────────────────────────────────────────────────────

export const Dashboard = ({ setPage }: WithSetPage) => {
  const [cases,         setCases]         = useState<Case[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState<string | null>(null);
  const [deleteTarget,  setDeleteTarget]  = useState<string | null>(null); // case_id aus der API
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Echte Cases vom Backend laden
  useEffect(() => {
    casesApi.list()
      .then(res => setCases(res.cases.map(mapApiCase)))
      .catch(() => setError("Fälle konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  const handleNewCase = async () => {
    try {
      const res = await casesApi.create();
      // Neuen Fall in die Liste einfügen und direkt zum Case-Flow weiterleiten
      setCases(prev => [
        { id: res.case_id.slice(-6).toUpperCase(), date: new Date().toLocaleDateString("de-DE"), operator: "Netzbetreiber unbekannt", status: "Entwurf" },
        ...prev,
      ]);
      setPage("case");
    } catch {
      setError("Neuer Fall konnte nicht angelegt werden.");
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await casesApi.delete(deleteTarget);
      // Fall aus der lokalen Liste entfernen (ID ist die kurze UI-ID)
      setCases(prev => prev.filter(c => !deleteTarget.includes(c.id.toLowerCase())));
    } catch {
      setError("Fall konnte nicht gelöscht werden.");
    } finally {
      setDeleteLoading(false);
      setDeleteTarget(null);
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      setPage("landing");
    }
  };

  return (
    <>
      {deleteTarget && (
        <DeleteModal
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          loading={deleteLoading}
        />
      )}

      <div style={{ display: "flex", minHeight: "calc(100vh - 60px)" }}>
        <Sidebar setPage={setPage} onLogout={handleLogout} onNewCase={handleNewCase} />

        <div style={{ flex: 1, padding: 28, overflowY: "auto" }}>
          <WelcomeCard onNewCase={handleNewCase} />

          {/* Error */}
          {error && (
            <div style={{
              marginBottom: 16,
              padding:      "12px 16px",
              background:   "#FDF2F2",
              border:       "1px solid #F5C6C5",
              borderRadius: 10,
              color:        "#D9534F",
              fontSize:     13,
              fontFamily:   typography.sans,
            }}>
              {error}
            </div>
          )}

          {/* Case list header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={textStyles.h3}>Deine Fälle</h3>
            <div style={{ display: "flex", gap: 10 }}>
              <Button variant="outline" size="sm">
                <Icon name="export" size={13} color={colors.mid} /> Export
              </Button>
              <Button size="sm" onClick={handleNewCase}>
                <Icon name="plus" size={13} color="#fff" /> Neuen Fall
              </Button>
            </div>
          </div>

          {/* Loading */}
          {loading && (
            <p style={{ ...textStyles.body, color: colors.muted, textAlign: "center", padding: 48 }}>
              Lade Fälle…
            </p>
          )}

          {/* Empty state */}
          {!loading && cases.length === 0 && !error && (
            <div style={{
              textAlign:    "center",
              padding:      64,
              background:   colors.white,
              borderRadius: 12,
              border:       `1px dashed ${colors.border}`,
            }}>
              <p style={{ ...textStyles.body, color: colors.muted, marginBottom: 20 }}>
                Noch keine Fälle vorhanden.
              </p>
              <Button onClick={handleNewCase}>
                <Icon name="plus" size={14} color="#fff" /> Ersten Fall starten
              </Button>
            </div>
          )}

          {/* Case Grid */}
          {!loading && cases.length > 0 && (
            <div style={{
              display:             "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap:                 16,
            }}>
              {cases.map(c => (
                <CaseCard
                  key={c.id}
                  c={c}
                  setPage={setPage}
                  onDelete={() => setDeleteTarget(c.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
};
