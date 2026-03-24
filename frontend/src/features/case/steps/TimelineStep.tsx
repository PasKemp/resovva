import { useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Badge, Card, Icon } from "../../../components";
import type { TimelineEvent } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 3 — Der Rote Faden (Chronologie)
// ─────────────────────────────────────────────────────────────────────────────

const INITIAL_EVENTS: TimelineEvent[] = [
  { date: "02.03.2026", event: "Rechnung empfangen: Abschlagsrechnung 02/2026", source: "E-Mail" },
  { date: "15.02.2026", event: "Zählerstand fotografiert",                      source: "Foto" },
  { date: "01.01.2026", event: "Vertrag geändert: Tarifwechsel",                source: "Post" },
];

const SOURCE_BADGE_COLOR: Record<TimelineEvent["source"], "teal" | "orange" | "muted"> = {
  "E-Mail":    "teal",
  "Foto":      "orange",
  "Post":      "muted",
  "Telefonat": "muted",
  "Sonstiges": "muted",
};

interface TimelineStepProps {
  caseId: string;
  onNext: () => void;
  onBack: () => void;
}

export const TimelineStep = ({ caseId: _caseId, onNext, onBack }: TimelineStepProps) => {
  const [events, setEvents] = useState<TimelineEvent[]>(INITIAL_EVENTS);

  const addManualEvent = () => {
    setEvents(prev => [...prev, {
      date:   new Date().toLocaleDateString("de-DE"),
      event:  "Telefonat mit Netzbetreiber",
      source: "Telefonat",
    }]);
  };

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>3. Der Rote Faden</h3>

        {/* ── Gap warning ── */}
        <div style={{
          background:   colors.yellow,
          border:       `1px solid ${colors.yellowBorder}`,
          borderRadius: 8,
          padding:      "12px 16px",
          display:      "flex",
          alignItems:   "center",
          justifyContent: "space-between",
          marginBottom: 20,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="warn" size={18} color={colors.yellowText} />
            <span style={{
              fontSize:   13,
              fontFamily: typography.sans,
              color:      colors.yellowText,
            }}>
              Es scheint eine Rechnung vom 01.03. zu fehlen.
            </span>
          </div>
          <Button variant="outline" size="sm">Nachreichen</Button>
        </div>

        {/* ── Timeline table ── */}
        <div style={{
          border:       `1px solid ${colors.border}`,
          borderRadius: 8,
          overflow:     "hidden",
        }}>
          {/* Header */}
          <div style={{
            display:             "grid",
            gridTemplateColumns: "130px 1fr 90px",
            background:          colors.bg,
            padding:             "10px 16px",
            borderBottom:        `1px solid ${colors.border}`,
          }}>
            {["Datum", "Ereignis", "Quelle"].map(h => (
              <span key={h} style={textStyles.label}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          {events.map((row, i) => (
            <div
              key={i}
              style={{
                display:             "grid",
                gridTemplateColumns: "130px 1fr 90px",
                padding:             "13px 16px",
                borderBottom:        i < events.length - 1 ? `1px solid ${colors.border}` : "none",
                alignItems:          "center",
                transition:          "background .15s",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = colors.bg)}
              onMouseLeave={e => (e.currentTarget.style.background = "")}
            >
              <span style={{ fontSize: 13, color: colors.mid, fontFamily: typography.sans }}>
                {row.date}
              </span>
              <span style={{ fontSize: 13, color: colors.dark, fontFamily: typography.sans }}>
                {row.event}
              </span>
              <Badge color={SOURCE_BADGE_COLOR[row.source]}>
                {row.source}
              </Badge>
            </div>
          ))}
        </div>

        {/* Add manual event */}
        <div style={{ marginTop: 14, display: "flex", justifyContent: "flex-end" }}>
          <Button variant="outline" size="sm" onClick={addManualEvent}>
            <Icon name="plus" size={13} color={colors.mid} />
            Manuelles Ereignis (z. B. Telefonat)
          </Button>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Button variant="outline" onClick={onBack}>Zurück</Button>
        <Button onClick={onNext} size="lg">
          Zum Checkout <Icon name="arrow" size={15} color="#fff" />
        </Button>
      </div>
    </div>
  );
};
