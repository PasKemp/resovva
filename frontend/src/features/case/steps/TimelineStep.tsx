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

// Spec: E-Mail=blau, Post=grau, Foto=orange, Eigene Angabe=lila
const SOURCE_BADGE_COLOR: Record<TimelineEvent["source"], "blue" | "orange" | "muted" | "purple"> = {
  "E-Mail":        "blue",
  "Foto":          "orange",
  "Post":          "muted",
  "Telefonat":     "muted",
  "Sonstiges":     "muted",
  "Eigene Angabe": "purple",
};

const SOURCE_OPTIONS: TimelineEvent["source"][] = ["E-Mail", "Post", "Foto", "Telefonat", "Eigene Angabe", "Sonstiges"];

interface TimelineStepProps {
  caseId: string;
  onNext: () => void;
  onBack: () => void;
}

// ── Add-Event-Modal ───────────────────────────────────────────────────────────

interface AddEventModalProps {
  onSave:  (e: TimelineEvent) => void;
  onClose: () => void;
}

const AddEventModal = ({ onSave, onClose }: AddEventModalProps) => {
  const [date,   setDate]   = useState(new Date().toISOString().split("T")[0]);
  const [event,  setEvent]  = useState("");
  const [source, setSource] = useState<TimelineEvent["source"]>("Eigene Angabe");

  const handleSave = () => {
    if (!event.trim()) return;
    const [y, m, d] = date.split("-");
    onSave({ date: `${d}.${m}.${y}`, event: event.trim(), source });
    onClose();
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: colors.white, borderRadius: 16, padding: 28,
          width: 420, boxShadow: "0 16px 64px rgba(0,0,0,.12)",
        }}
      >
        <p style={{ fontFamily: typography.sans, fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 20 }}>
          Manuelles Ereignis hinzufügen
        </p>

        <div style={{ marginBottom: 14 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Datum</label>
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            style={{
              width: "100%", padding: "9px 12px", fontFamily: typography.sans, fontSize: 13,
              border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
              background: colors.bg, color: colors.dark, boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Beschreibung</label>
          <textarea
            value={event}
            onChange={e => setEvent(e.target.value)}
            placeholder="z. B. Telefonat mit Kundenservice, Kündigung eingereicht…"
            rows={3}
            style={{
              width: "100%", padding: "9px 12px", fontFamily: typography.sans, fontSize: 13,
              border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
              background: colors.bg, color: colors.dark, resize: "vertical", boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ marginBottom: 22 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Quelle</label>
          <select
            value={source}
            onChange={e => setSource(e.target.value as TimelineEvent["source"])}
            style={{
              width: "100%", padding: "9px 12px", fontFamily: typography.sans, fontSize: 13,
              border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
              background: colors.bg, color: colors.dark, cursor: "pointer",
            }}
          >
            {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={!event.trim()}>Hinzufügen</Button>
        </div>
      </div>
    </div>
  );
};

// ── Timeline row ──────────────────────────────────────────────────────────────

const TimelineRow = ({
  row, index, total, onDelete,
}: {
  row: TimelineEvent; index: number; total: number; onDelete: (i: number) => void;
}) => {
  const [hovered,  setHovered]  = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setMenuOpen(false); }}
      style={{
        display:             "grid",
        gridTemplateColumns: "130px 1fr 110px 32px",
        padding:             "12px 16px",
        borderBottom:        index < total - 1 ? `1px solid ${colors.border}` : "none",
        alignItems:          "center",
        background:          hovered ? colors.bg : "transparent",
        transition:          "background .15s",
        position:            "relative",
      }}
    >
      <span style={{ fontSize: 13, color: colors.mid, fontFamily: typography.sans }}>
        {row.date}
      </span>
      <span style={{ fontSize: 13, color: colors.dark, fontFamily: typography.sans }}>
        {row.event}
      </span>
      <Badge color={SOURCE_BADGE_COLOR[row.source] ?? "muted"}>
        {row.source}
      </Badge>
      <div style={{ position: "relative" }}>
        <button
          onClick={() => setMenuOpen(m => !m)}
          style={{
            background: "none", border: "none", cursor: "pointer",
            width: 28, height: 28, borderRadius: 6,
            display: "flex", alignItems: "center", justifyContent: "center",
            opacity: hovered ? 1 : 0, transition: "opacity .15s",
            color: colors.muted, fontSize: 16, fontFamily: typography.sans,
          }}
        >
          ···
        </button>
        {menuOpen && (
          <div style={{
            position: "absolute", right: 0, top: 32, zIndex: 10,
            background: colors.white, border: `1px solid ${colors.border}`,
            borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,.08)",
            minWidth: 130, overflow: "hidden",
          }}>
            <button
              onClick={() => setMenuOpen(false)}
              style={{
                width: "100%", padding: "9px 14px", background: "none", border: "none",
                textAlign: "left", fontFamily: typography.sans, fontSize: 13, color: colors.dark, cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = colors.bg)}
              onMouseLeave={e => (e.currentTarget.style.background = "none")}
            >
              Bearbeiten
            </button>
            <button
              onClick={() => { onDelete(index); setMenuOpen(false); }}
              style={{
                width: "100%", padding: "9px 14px", background: "none", border: "none",
                textAlign: "left", fontFamily: typography.sans, fontSize: 13, color: colors.redText, cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#FEF2F2")}
              onMouseLeave={e => (e.currentTarget.style.background = "none")}
            >
              Löschen
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────

export const TimelineStep = ({ caseId: _caseId, onNext: _onNext, onBack: _onBack }: TimelineStepProps) => {
  const [events,   setEvents]   = useState<TimelineEvent[]>(INITIAL_EVENTS);
  const [showModal, setShowModal] = useState(false);

  const addEvent = (e: TimelineEvent) => setEvents(prev => [...prev, e]);
  const deleteEvent = (index: number) => setEvents(prev => prev.filter((_, i) => i !== index));

  return (
    <div className="fade-in">
      {showModal && <AddEventModal onSave={addEvent} onClose={() => setShowModal(false)} />}

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 20 }}>3. Der Rote Faden</h3>

        {/* ── Gap warning ── */}
        <div style={{
          background: colors.yellow, border: `1px solid ${colors.yellowBorder}`,
          borderRadius: 8, padding: "12px 16px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginBottom: 20,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="warn" size={18} color={colors.yellowText} />
            <span style={{ fontSize: 13, fontFamily: typography.sans, color: colors.yellowText }}>
              Es scheint eine Rechnung vom 01.03. zu fehlen.
            </span>
          </div>
          <Button variant="outline" size="sm">Nachreichen</Button>
        </div>

        {/* ── Timeline table ── */}
        <div style={{ border: `1px solid ${colors.border}`, borderRadius: 8, overflow: "hidden" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "130px 1fr 110px 32px",
            background: colors.bg, padding: "10px 16px",
            borderBottom: `1px solid ${colors.border}`,
          }}>
            {["Datum", "Ereignis", "Quelle", ""].map((h, i) => (
              <span key={i} style={textStyles.label}>{h}</span>
            ))}
          </div>

          {events.map((row, i) => (
            <TimelineRow key={i} row={row} index={i} total={events.length} onDelete={deleteEvent} />
          ))}
        </div>

        {/* ── Add manual event (dashed ghost button) ── */}
        <div style={{ marginTop: 14 }}>
          <button
            onClick={() => setShowModal(true)}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              width: "100%", padding: "10px 14px",
              background: "transparent", border: `1.5px dashed ${colors.border}`,
              borderRadius: 8, cursor: "pointer",
              fontFamily: typography.sans, fontSize: 13, color: colors.muted,
              transition: "border-color .15s, color .15s",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = colors.orange;
              (e.currentTarget as HTMLButtonElement).style.color = colors.orange;
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = colors.border;
              (e.currentTarget as HTMLButtonElement).style.color = colors.muted;
            }}
          >
            <Icon name="plus" size={14} color="inherit" />
            + Manuelles Ereignis hinzufügen
          </button>
        </div>

        {/* ── Divider ── */}
        <div style={{ borderTop: `1px solid ${colors.border}`, margin: "20px 0" }} />

        {/* ── Conclusion section ── */}
        <div>
          <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark, marginBottom: 4 }}>
            Alle Ereignisse korrekt?
          </p>
          <p style={{ ...textStyles.body, fontSize: 13 }}>
            Jetzt zum Checkout und Dossier erstellen lassen.
          </p>
        </div>
      </Card>
    </div>
  );
};
