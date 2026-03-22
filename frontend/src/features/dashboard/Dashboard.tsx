import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Badge, Card, Icon } from "../../components";
import type { Case, CaseStatus, WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────────────────────

// ── Mock data ────────────────────────────────────────────────────────────────
// TODO: replace with useCases() hook that calls casesApi.list()

const CASES: Case[] = [
  { id: "2026-14", date: "12.03.2026", operator: "Energie Nord GmbH",  status: "Entwurf" },
  { id: "2026-09", date: "02.02.2026", operator: "Stadtwerke Berlin",  status: "Wartet auf Zahlung" },
  { id: "2025-78", date: "15.11.2025", operator: "RheinEnergie AG",    status: "Abgeschlossen" },
  { id: "2026-21", date: "18.03.2026", operator: "NordNetz AG",        status: "Entwurf" },
];

const ACTIVITIES = [
  "Anna M. hat Dokumente hochgeladen · 2 Std.",
  "Analyse abgeschlossen für Fall #2026-14 · 1 Tag",
  "Neues Ticket: Rückfrage Netzbetreiber · 3 Tage",
];

const STATUS_COLOR: Record<CaseStatus, "orange" | "yellow" | "teal"> = {
  Entwurf:                "orange",
  "Wartet auf Zahlung":   "yellow",
  Abgeschlossen:          "teal",
};

// ── Sub-components ─────────────────────────────────────────────────────────

const Sidebar = ({ setPage }: WithSetPage) => (
  <div style={{
    width:       224,
    background:  colors.white,
    borderRight: `1px solid ${colors.border}`,
    padding:     22,
    flexShrink:  0,
  }}>
    <h3 style={{ ...textStyles.h3, fontSize: 15, marginBottom: 4 }}>Übersicht</h3>
    <p style={{ ...textStyles.small, marginBottom: 20 }}>
      Deine Fälle, Status und Schnellaktionen
    </p>

    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      <Button onClick={() => setPage("case")} size="sm" style={{ justifyContent: "center" }}>
        <Icon name="plus"     size={14} color="#fff" /> Neuen Fall starten
      </Button>
      <Button variant="outline" size="sm" style={{ justifyContent: "center" }}>
        <Icon name="import"   size={14} color={colors.mid} /> Importieren
      </Button>
      <Button variant="outline" size="sm" style={{ justifyContent: "center" }}>
        <Icon name="template" size={14} color={colors.mid} /> Vorlagen
      </Button>
    </div>

    <div style={{ marginTop: 32 }}>
      <p style={{ ...textStyles.label, marginBottom: 13 }}>Letzte Aktivitäten</p>
      {ACTIVITIES.map((a, i) => (
        <div key={i} style={{ display: "flex", gap: 9, marginBottom: 11, alignItems: "flex-start" }}>
          <div style={{
            width: 6, height: 6, borderRadius: "50%",
            background: colors.orange, marginTop: 5, flexShrink: 0,
          }} />
          <p style={{ fontSize: 11, color: colors.muted, lineHeight: 1.5, fontFamily: typography.sans }}>
            {a}
          </p>
        </div>
      ))}
    </div>
  </div>
);

const WelcomeCard = ({ setPage }: WithSetPage) => (
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
          <Button onClick={() => setPage("case")} size="md">
            <Icon name="plus" size={14} color="#fff" /> Neuen Fall starten
          </Button>
          <Button variant="outline" size="md">Hilfe ansehen</Button>
        </div>
      </div>

      {/* Quick-action icons */}
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

const CaseCard = ({ c, setPage }: { c: Case; setPage: (p: any) => void }) => {
  const isEditable    = c.status === "Entwurf";
  const isDownloadable= c.status !== "Entwurf";

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
      </div>
    </div>
  );
};

// ── Dashboard ──────────────────────────────────────────────────────────────

export const Dashboard = ({ setPage }: WithSetPage) => (
  <div style={{ display: "flex", minHeight: "calc(100vh - 60px)" }}>
    <Sidebar setPage={setPage} />

    <div style={{ flex: 1, padding: 28, overflowY: "auto" }}>
      <WelcomeCard setPage={setPage} />

      {/* Case list header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={textStyles.h3}>Deine Fälle</h3>
        <div style={{ display: "flex", gap: 10 }}>
          <Button variant="outline" size="sm">
            <Icon name="export" size={13} color={colors.mid} /> Export
          </Button>
          <Button size="sm" onClick={() => setPage("case")}>
            <Icon name="plus" size={13} color="#fff" /> Neuen Fall
          </Button>
        </div>
      </div>

      <div style={{
        display:             "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap:                 16,
      }}>
        {CASES.map(c => (
          <CaseCard key={c.id} c={c} setPage={setPage} />
        ))}
      </div>
    </div>
  </div>
);
