import React, { useCallback, useEffect, useRef, useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Badge, Card, Icon } from "../../../components";
import { AddEventModal } from "../../../components/AddEventModal";
import { timelineApi } from "../../../services/api";
import type { TimelineEvent } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 3 — Der Rote Faden (Chronologie)
// ─────────────────────────────────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  ai:   "KI-Extraktion",
  user: "Eigene Angabe",
};

const SOURCE_BADGE_COLOR: Record<string, "blue" | "orange" | "muted" | "purple"> = {
  ai:   "muted",
  user: "purple",
};

/** ISO "YYYY-MM-DD" → "DD.MM.YYYY" */
const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
};

interface TimelineStepProps {
  caseId: string;
  onNext: () => void;
  onBack: () => void;
  onGoToUpload?: () => void;
}

// ── Edit-Modal (wiederverwendet für Add & Edit) ───────────────────────────────

interface EditEventModalProps {
  initialDate:        string;
  initialDescription: string;
  onSave:             (payload: { event_date: string; description: string }) => Promise<void>;
  onClose:            () => void;
}

const EditEventModal: React.FC<EditEventModalProps> = ({
  initialDate, initialDescription, onSave, onClose,
}) => {
  const today = new Date().toISOString().split("T")[0];
  const [eventDate,   setEventDate]   = useState(initialDate);
  const [description, setDescription] = useState(initialDescription);
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const charsLeft = 500 - description.length;

  const handleSave = async () => {
    if (!description.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onSave({ event_date: eventDate, description: description.trim() });
      onClose();
    } catch {
      setError("Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,.35)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: colors.white, borderRadius: 16, padding: 28,
          width: 420, boxShadow: "0 16px 64px rgba(0,0,0,.12)",
        }}
      >
        <p style={{ fontFamily: typography.sans, fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 20 }}>
          Ereignis bearbeiten
        </p>
        {error && (
          <p style={{ fontSize: 12, color: colors.redText, fontFamily: typography.sans, marginBottom: 12 }}>{error}</p>
        )}
        <div style={{ marginBottom: 14 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Datum</label>
          <input
            type="date" value={eventDate} max={today}
            onChange={e => setEventDate(e.target.value)}
            style={{
              width: "100%", padding: "9px 12px", fontFamily: typography.sans, fontSize: 13,
              border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
              background: colors.bg, color: colors.dark, boxSizing: "border-box",
            }}
          />
        </div>
        <div style={{ marginBottom: 22 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>
            Beschreibung
            <span style={{ fontWeight: 400, color: colors.muted, marginLeft: 6 }}>({charsLeft} Zeichen übrig)</span>
          </label>
          <textarea
            value={description} onChange={e => setDescription(e.target.value)}
            maxLength={500} rows={3}
            style={{
              width: "100%", padding: "9px 12px", fontFamily: typography.sans, fontSize: 13,
              border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
              background: colors.bg, color: colors.dark, resize: "vertical", boxSizing: "border-box",
            }}
          />
        </div>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <Button variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={!description.trim() || saving}>
            {saving ? "Speichern…" : "Speichern"}
          </Button>
        </div>
      </div>
    </div>
  );
};

// ── Gap-Row ───────────────────────────────────────────────────────────────────

const GapRow: React.FC<{
  row:      TimelineEvent;
  isLast:   boolean;
  onIgnore: (id: string) => void;
  onUpload: () => void;
}> = ({ row, isLast, onIgnore, onUpload }) => (
  <div style={{
    display:      "flex",
    alignItems:   "center",
    justifyContent: "space-between",
    padding:      "12px 16px",
    borderBottom: isLast ? "none" : `1px solid ${colors.border}`,
    background:   colors.yellow,
    gap:          12,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
      <Icon name="warn" size={16} color={colors.yellowText} />
      <div style={{ minWidth: 0 }}>
        <span style={{ fontSize: 12, color: colors.yellowText, fontFamily: typography.sans, fontWeight: 600 }}>
          {formatDate(row.event_date)} &nbsp;
        </span>
        <span style={{ fontSize: 13, color: colors.yellowText, fontFamily: typography.sans }}>
          {row.description}
        </span>
      </div>
    </div>
    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
      <Button size="sm" variant="outline" onClick={onUpload}>
        Nachreichen
      </Button>
      <Button size="sm" variant="ghost" onClick={() => onIgnore(row.event_id)}>
        Ignorieren
      </Button>
    </div>
  </div>
);

// ── Normal-Row (AI & User) ────────────────────────────────────────────────────

const TimelineRow: React.FC<{
  row:      TimelineEvent;
  isLast:   boolean;
  onDelete: (id: string) => void;
  onEdit:   (row: TimelineEvent) => void;
}> = ({ row, isLast, onDelete, onEdit }) => {
  const [hovered,  setHovered]  = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setMenuOpen(false); }}
      style={{
        display:             "grid",
        gridTemplateColumns: "120px 1fr 120px 32px",
        padding:             "12px 16px",
        borderBottom:        isLast ? "none" : `1px solid ${colors.border}`,
        alignItems:          "center",
        background:          hovered ? colors.bg : "transparent",
        transition:          "background .15s",
        position:            "relative",
      }}
    >
      <span style={{ fontSize: 13, color: colors.mid, fontFamily: typography.sans }}>
        {formatDate(row.event_date)}
      </span>
      <span style={{ fontSize: 13, color: colors.dark, fontFamily: typography.sans, paddingRight: 12 }}>
        {row.description}
      </span>
      <Badge color={SOURCE_BADGE_COLOR[row.source_type] ?? "muted"}>
        {SOURCE_LABEL[row.source_type] ?? row.source_type}
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
              onClick={() => { onEdit(row); setMenuOpen(false); }}
              style={{
                width: "100%", padding: "9px 14px", background: "none", border: "none",
                textAlign: "left", fontFamily: typography.sans, fontSize: 13,
                color: colors.dark, cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = colors.bg)}
              onMouseLeave={e => (e.currentTarget.style.background = "none")}
            >
              Bearbeiten
            </button>
            <button
              onClick={() => { onDelete(row.event_id); setMenuOpen(false); }}
              style={{
                width: "100%", padding: "9px 14px", background: "none", border: "none",
                textAlign: "left", fontFamily: typography.sans, fontSize: 13,
                color: colors.redText, cursor: "pointer",
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

/**
 * Step 3: Interaktive Chronologie-Ansicht (US-4.3).
 *
 * - Pollt timeline API solange status='building'
 * - Zeigt Gap-Rows (gelb) mit Nachreichen/Ignorieren-Buttons
 * - AI-Events: 3-Punkt-Menü (Bearbeiten, Löschen)
 * - User-Events: Badge "Eigene Angabe", gleiche Optionen
 */
export const TimelineStep: React.FC<TimelineStepProps> = ({ caseId, onNext, onBack, onGoToUpload }) => {
  const [events,         setEvents]         = useState<TimelineEvent[]>([]);
  const [timelineStatus, setTimelineStatus] = useState<"building" | "ready" | "empty">("building");
  const [showAddModal,   setShowAddModal]   = useState(false);
  const [editTarget,     setEditTarget]     = useState<TimelineEvent | null>(null);
  const [error,          setError]          = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Polling-Logik
  const loadTimeline = useCallback(() => {
    timelineApi.get(caseId)
      .then(r => {
        setEvents(r.events);
        setTimelineStatus(r.status);
        if (r.status !== "building" && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      })
      .catch(() => {
        setError("Timeline konnte nicht geladen werden.");
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      });
  }, [caseId]);

  useEffect(() => {
    loadTimeline();
    pollRef.current = setInterval(loadTimeline, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadTimeline]);

  const handleAddEvent = useCallback((event: TimelineEvent) => {
    setEvents(prev => {
      const updated = [...prev, event];
      return updated.sort((a, b) => {
        if (!a.event_date) return 1;
        if (!b.event_date) return -1;
        return a.event_date.localeCompare(b.event_date);
      });
    });
    if (timelineStatus === "empty") setTimelineStatus("ready");
  }, [timelineStatus]);

  const handleDeleteEvent = useCallback(async (id: string) => {
    setEvents(prev => prev.filter(e => e.event_id !== id));
    try {
      await timelineApi.deleteEvent(caseId, id);
    } catch {
      setError("Löschen fehlgeschlagen.");
    }
  }, [caseId]);

  const handleEditEvent = useCallback(async (payload: { event_date: string; description: string }) => {
    if (!editTarget) return;
    const updated = await timelineApi.updateEvent(caseId, editTarget.event_id, payload);
    setEvents(prev => prev.map(e => e.event_id === updated.event_id ? updated : e));
  }, [caseId, editTarget]);

  const isBuilding = timelineStatus === "building";

  return (
    <div className="fade-in">
      {showAddModal && (
        <AddEventModal
          caseId={caseId}
          onSave={handleAddEvent}
          onClose={() => setShowAddModal(false)}
        />
      )}
      {editTarget && (
        <EditEventModal
          initialDate={editTarget.event_date ?? new Date().toISOString().split("T")[0]}
          initialDescription={editTarget.description}
          onSave={handleEditEvent}
          onClose={() => setEditTarget(null)}
        />
      )}

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 20 }}>3. Der Rote Faden</h3>

        {error && (
          <p style={{ fontSize: 12, color: colors.redText, fontFamily: typography.sans, marginBottom: 12 }}>
            {error}
          </p>
        )}

        {/* ── Lade-Indikator ── */}
        {isBuilding ? (
          <div style={{
            background: colors.yellow, border: `1px solid ${colors.yellowBorder}`,
            borderRadius: 8, padding: "14px 16px",
            display: "flex", alignItems: "center", gap: 12, marginBottom: 20,
          }}>
            <div style={{
              width: 16, height: 16, border: `2px solid ${colors.yellowText}`,
              borderTopColor: "transparent", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", flexShrink: 0,
            }} />
            <span style={{ fontSize: 13, fontFamily: typography.sans, color: colors.yellowText }}>
              KI erstellt Chronologie – bitte kurz warten…
            </span>
          </div>
        ) : null}

        {/* ── Timeline-Tabelle ── */}
        {!isBuilding && (
          <div style={{ border: `1px solid ${colors.border}`, borderRadius: 8, overflow: "hidden", marginBottom: 14 }}>
            {/* Header */}
            <div style={{
              display: "grid", gridTemplateColumns: "120px 1fr 120px 32px",
              background: colors.bg, padding: "10px 16px",
              borderBottom: `1px solid ${colors.border}`,
            }}>
              {["Datum", "Ereignis", "Quelle", ""].map((h, i) => (
                <span key={i} style={textStyles.label}>{h}</span>
              ))}
            </div>

            {events.length === 0 && (
              <p style={{ ...textStyles.small, color: colors.muted, padding: "16px", textAlign: "center" }}>
                Noch keine Ereignisse vorhanden.
              </p>
            )}

            {events.map((row, i) =>
              row.is_gap ? (
                <GapRow
                  key={row.event_id}
                  row={row}
                  isLast={i === events.length - 1}
                  onIgnore={handleDeleteEvent}
                  onUpload={onGoToUpload ?? onBack}
                />
              ) : (
                <TimelineRow
                  key={row.event_id}
                  row={row}
                  isLast={i === events.length - 1}
                  onDelete={handleDeleteEvent}
                  onEdit={setEditTarget}
                />
              )
            )}
          </div>
        )}

        {/* ── Manuelles Ereignis hinzufügen ── */}
        {!isBuilding && (
          <div style={{ marginBottom: 20 }}>
            <button
              onClick={() => setShowAddModal(true)}
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
        )}

        {/* ── Divider + CTA ── */}
        <div style={{ borderTop: `1px solid ${colors.border}`, margin: "20px 0" }} />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark, marginBottom: 4 }}>
              Alle Ereignisse korrekt?
            </p>
            <p style={{ ...textStyles.body, fontSize: 13 }}>
              Jetzt zum Checkout und Dossier erstellen lassen.
            </p>
          </div>
          <Button onClick={onNext} disabled={isBuilding}>
            Weiter zum Checkout
          </Button>
        </div>
      </Card>
    </div>
  );
};
