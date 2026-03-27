import { useEffect, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Badge, Card, Icon } from "../../components";
import { casesApi } from "../../services/api";
import { mapApiCase } from "../../types";
import type { Case, CaseStatus, WithSetPage } from "../../types";

interface DashboardProps extends WithSetPage {
  openCase: (caseId?: string, step?: number) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard (US-7.5: Sidebar-Navigation & Fall-Vorschau, US-7.6: Delete-Bug-Fix)
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<CaseStatus, "orange" | "yellow" | "teal"> = {
  Entwurf:                "orange",
  "Wartet auf Zahlung":   "yellow",
  "Zahlung ausstehend":   "yellow",
  Abgeschlossen:          "teal",
};

// CTA je Status (US-7.5 + US-5.4)
const STATUS_CTA: Record<CaseStatus, string> = {
  Entwurf:                "Weiter zur Analyse",
  "Wartet auf Zahlung":   "Daten bestätigen",
  "Zahlung ausstehend":   "Zahlung abschließen",
  Abgeschlossen:          "Dossier herunterladen",
};

// Checkout-Schritt für PAYMENT_PENDING-Retry (US-5.4)
const STATUS_STEP: Partial<Record<CaseStatus, number>> = {
  "Zahlung ausstehend": 3,
};

// ── Delete-Confirm-Modal ─────────────────────────────────────────────────────

const DeleteModal = ({
  onConfirm, onCancel, loading,
}: { onConfirm: () => void; onCancel: () => void; loading: boolean }) => (
  <div style={{
    position: "fixed", inset: 0,
    background: "rgba(0,0,0,.45)", zIndex: 1000,
    display: "flex", alignItems: "center", justifyContent: "center",
  }}>
    <div style={{
      background: colors.white, borderRadius: 16, padding: "36px 32px",
      maxWidth: 440, width: "90%", boxShadow: "0 24px 80px rgba(0,0,0,.2)",
    }}>
      <h3 style={{ ...textStyles.h3, marginBottom: 12, color: colors.danger }}>
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
          size="md" onClick={onConfirm} disabled={loading}
          style={{ background: colors.danger, color: "#fff" }}
        >
          {loading ? "Löschen…" : "Ja, dauerhaft löschen"}
        </Button>
      </div>
    </div>
  </div>
);

// ── Case-Sidebar ─────────────────────────────────────────────────────────────

const CaseSidebar = ({
  cases,
  selectedId,
  onSelect,
  onNewCase,
  loading,
}: {
  cases:      Case[];
  selectedId: string | null;
  onSelect:   (c: Case) => void;
  onNewCase:  () => void;
  loading:    boolean;
}) => (
  <div style={{
    width:          280,               // US-7.5: 280px fix
    background:     colors.white,
    borderRight:    `1px solid ${colors.border}`,
    display:        "flex",
    flexDirection:  "column",
    flexShrink:     0,
    overflowY:      "auto",           // US-7.5: scrollbar bei vielen Fällen
  }}>
    {/* Header */}
    <div style={{ padding: "20px 20px 12px", borderBottom: `1px solid ${colors.border}` }}>
      <h3 style={{ ...textStyles.h3, fontSize: 15, marginBottom: 2 }}>Meine Fälle</h3>
      <p style={{ ...textStyles.small }}>
        {loading ? "Lädt…" : `${cases.length} Fall${cases.length !== 1 ? "e" : ""}`}
      </p>
    </div>

    {/* Neuer Fall – prominenter Button oben */}
    <div style={{ padding: "12px 12px 4px" }}>
      <Button onClick={onNewCase} size="sm" style={{ width: "100%", justifyContent: "center" }}>
        <Icon name="plus" size={13} color="#fff" /> Neuer Fall
      </Button>
    </div>

    {/* Case-Liste */}
    <div style={{ flex: 1, padding: "4px 10px 8px" }}>
      {!loading && cases.length === 0 && (
        <p style={{ ...textStyles.small, color: colors.muted, textAlign: "center", padding: "24px 12px" }}>
          Noch keine Fälle vorhanden.
        </p>
      )}

      {cases.map(c => {
        const isSelected = c.apiId === selectedId;
        return (
          <div
            key={c.apiId}
            onClick={() => onSelect(c)}
            style={{
              padding:      "12px 12px",
              borderRadius: 10,
              marginBottom: 4,
              cursor:       "pointer",
              background:   isSelected ? colors.orangeLight : "transparent",
              borderLeft:   `3px solid ${isSelected ? colors.orange : "transparent"}`,
              transition:   "all .15s",
            }}
            onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = colors.bg; }}
            onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <span style={{
                fontFamily: typography.sans,
                fontSize:   13,
                fontWeight: 600,
                color:      colors.dark,
              }}>
                Fall #{c.id}
              </span>
              <Badge color={STATUS_COLOR[c.status]}>
                {c.status}
              </Badge>
            </div>
            <p style={{ ...textStyles.small, marginTop: 3, color: colors.muted }}>
              {c.date} · {c.documentCount} Dok.
            </p>
          </div>
        );
      })}
    </div>

  </div>
);

// ── CasePreview ──────────────────────────────────────────────────────────────

const CasePreview = ({
  c,
  onOpen,
  onDelete,
}: {
  c:        Case;
  onOpen:   (step?: number) => void;
  onDelete: () => void;
}) => (
  <Card style={{ marginBottom: 24 }}>
    {/* Header */}
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
      <div>
        <p style={{ ...textStyles.label, marginBottom: 4 }}>Ausgewählter Fall</p>
        <h2 style={{ ...textStyles.h2, fontSize: 22 }}>Fall #{c.id}</h2>
      </div>
      <Badge color={STATUS_COLOR[c.status]}>{c.status}</Badge>
    </div>

    {/* Metadaten */}
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
      gap: 16, marginBottom: 24,
    }}>
      {([
        { label: "Erstellt",             value: c.date,                          icon: "activity" as const },
        { label: "Anbieter / Gegenseite", value: c.operator,                     icon: "scale"    as const },
        { label: "Dokumente",            value: `${c.documentCount} hochgeladen`, icon: "file"     as const },
      ]).map(({ label, value, icon }) => (
        <div key={label} style={{
          background: colors.white,
          borderRadius: 10,
          padding: "12px 14px",
          boxShadow: "0 1px 4px rgba(0,0,0,.08)",
          border: `1px solid ${colors.border}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
            <Icon name={icon} size={12} color={colors.muted} />
            <p style={{ ...textStyles.label, margin: 0 }}>{label}</p>
          </div>
          <p style={{ ...textStyles.body, fontSize: 13, fontWeight: 600, color: colors.dark }}>
            {value}
          </p>
        </div>
      ))}
    </div>

    {/* Nächste Aktion – CTA (US-7.5) */}
    <div style={{
      background:   colors.orangeLight,
      border:       `1px solid ${colors.orange}22`,
      borderRadius: 10,
      padding:      "14px 16px",
      display:      "flex",
      alignItems:   "center",
      justifyContent: "space-between",
      marginBottom: 20,
    }}>
      <div>
        <p style={{ ...textStyles.label, color: colors.orange, marginBottom: 2 }}>Nächste Aktion</p>
        <p style={{ ...textStyles.body, fontSize: 13, color: colors.dark, fontWeight: 600 }}>
          {STATUS_CTA[c.status]}
        </p>
      </div>
      <Button size="sm" onClick={() => onOpen(STATUS_STEP[c.status])}>
        {STATUS_CTA[c.status]} <Icon name="arrow" size={13} color="#fff" />
      </Button>
    </div>

    {/* Aktionen */}
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <Button variant="outline" size="sm" onClick={() => onOpen()}>
        <Icon name="file" size={13} color={colors.mid} /> Fall öffnen
      </Button>
      <button
        onClick={onDelete}
        style={{
          marginLeft:  "auto",
          background:  "none",
          border:      "none",
          padding:     "6px 4px",
          fontFamily:  typography.sans,
          fontSize:    13,
          fontWeight:  500,
          color:       colors.danger,
          cursor:      "pointer",
          display:     "flex",
          alignItems:  "center",
          gap:         5,
          opacity:     0.7,
          transition:  "opacity .15s",
        }}
        onMouseEnter={e => (e.currentTarget.style.opacity = "1")}
        onMouseLeave={e => (e.currentTarget.style.opacity = "0.7")}
      >
        <Icon name="x" size={13} color={colors.danger} /> Löschen
      </button>
    </div>
  </Card>
);

// ── WelcomeCard ──────────────────────────────────────────────────────────────

const WelcomeCard = ({ onNewCase }: { onNewCase: () => void }) => (
  <Card style={{ marginBottom: 24 }}>
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 24, alignItems: "start" }}>
      <div>
        <h2 style={{ ...textStyles.h2, fontSize: 21, marginBottom: 8 }}>
          Willkommen bei Resovva.
        </h2>
        <p style={{ ...textStyles.body, marginBottom: 20 }}>
          Wähle einen Fall aus der Sidebar oder starte einen neuen.
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
              width: 40, height: 40, background: colors.tealLight, borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name={icon} size={18} color={colors.teal} />
            </div>
            <span style={{
              fontSize: 11, color: colors.mid, textAlign: "center",
              whiteSpace: "pre", lineHeight: 1.4, fontFamily: typography.sans,
            }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  </Card>
);

// ── Dashboard ──────────────────────────────────────────────────────────────

export const Dashboard = ({ openCase }: DashboardProps) => {
  const [cases,         setCases]         = useState<Case[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState<string | null>(null);
  const [selectedCase,  setSelectedCase]  = useState<Case | null>(null);
  // US-7.6 Bug-Fix: deleteTarget speichert die vollständige UUID (apiId), nicht die kurze ID
  const [deleteTarget,  setDeleteTarget]  = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  // US-5.4: Toast bei Rückkehr von abgebrochener Stripe-Session
  const [paymentToast,  setPaymentToast]  = useState<"cancelled" | null>(null);

  // US-5.4: ?payment=cancelled Query-Param auswerten (nach Stripe-Redirect)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("payment") === "cancelled") {
      setPaymentToast("cancelled");
      window.history.replaceState({}, "", window.location.pathname);
      const t = setTimeout(() => setPaymentToast(null), 6000);
      return () => clearTimeout(t);
    }
  }, []);

  useEffect(() => {
    casesApi.list()
      .then(res => {
        const mapped = res.cases.map(mapApiCase);
        setCases(mapped);
        if (mapped.length > 0) setSelectedCase(mapped[0]);
      })
      .catch(() => setError("Fälle konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  // Neuer Fall: kein caseId übergeben → CaseFlow legt selbst an
  const handleNewCase = () => openCase(undefined);

  // Bestehenden Fall öffnen: step=3 für Checkout-Retry bei PAYMENT_PENDING (US-5.4)
  const handleOpenCase = (apiId: string, step?: number) => openCase(apiId, step);

  const handleDeleteRequest = (apiId: string) => {
    setDeleteTarget(apiId);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);

    // Optimistic UI: sofort aus Liste entfernen
    const previousCases = cases;
    const wasSelected = selectedCase?.apiId === deleteTarget;
    setCases(prev => prev.filter(c => c.apiId !== deleteTarget));
    if (wasSelected) setSelectedCase(null);

    try {
      // US-7.6 Fix: deleteTarget ist jetzt die vollständige UUID
      await casesApi.delete(deleteTarget);
    } catch {
      // Rollback bei Fehler
      setCases(previousCases);
      if (wasSelected) setSelectedCase(previousCases.find(c => c.apiId === deleteTarget) ?? null);
      setError("Löschen fehlgeschlagen – bitte erneut versuchen.");
    } finally {
      setDeleteLoading(false);
      setDeleteTarget(null);
    }
  };

  return (
    <>
      {/* US-5.4: Toast – Zahlung abgebrochen */}
      {paymentToast === "cancelled" && (
        <div style={{
          position:     "fixed",
          top:          80,
          left:         "50%",
          transform:    "translateX(-50%)",
          zIndex:       2000,
          background:   colors.white,
          border:       `1px solid ${colors.dangerBorder}`,
          borderRadius: 10,
          padding:      "12px 20px",
          boxShadow:    "0 8px 32px rgba(0,0,0,.12)",
          display:      "flex",
          alignItems:   "center",
          gap:          10,
          fontFamily:   typography.sans,
          fontSize:     13,
          color:        colors.danger,
          whiteSpace:   "nowrap",
        }}>
          <Icon name="x" size={14} color={colors.danger} />
          Zahlung wurde abgebrochen. Du kannst es jederzeit erneut versuchen.
          <button
            onClick={() => setPaymentToast(null)}
            style={{ background: "none", border: "none", cursor: "pointer", color: colors.muted, fontSize: 16, lineHeight: 1, padding: 0, marginLeft: 4 }}
          >
            ×
          </button>
        </div>
      )}

      {deleteTarget && (
        <DeleteModal
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          loading={deleteLoading}
        />
      )}

      <div style={{ display: "flex", height: "calc(100vh - 64px)", overflow: "hidden" }}>
        {/* ── Sidebar mit Fallliste (US-7.5) ── */}
        <CaseSidebar
          cases={cases}
          selectedId={selectedCase?.apiId ?? null}
          onSelect={setSelectedCase}
          onNewCase={handleNewCase}
          loading={loading}
        />

        {/* ── Hauptbereich ── */}
        <div style={{ flex: 1, padding: 28, overflowY: "auto" }}>

          {error && (
            <div style={{
              marginBottom: 16, padding: "12px 16px",
              background: colors.dangerLight, border: `1px solid ${colors.dangerBorder}`,
              borderRadius: 10, color: colors.danger, fontSize: 13, fontFamily: typography.sans,
            }}>
              {error}
            </div>
          )}

          {/* Fall-Vorschau (US-7.5) oder Welcome-Banner */}
          {selectedCase ? (
            <CasePreview
              c={selectedCase}
              onOpen={(step) => handleOpenCase(selectedCase.apiId, step)}
              onDelete={() => handleDeleteRequest(selectedCase.apiId)}
            />
          ) : (
            <WelcomeCard onNewCase={handleNewCase} />
          )}

        </div>
      </div>
    </>
  );
};
