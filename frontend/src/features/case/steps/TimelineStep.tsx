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

// ── Edit-Modal ─────────────────────────────────────────────────────────────────

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

// ── GapCard (gelbe Lücken-Hinweis-Karte) ──────────────────────────────────────

const GapCard: React.FC<{
  row:      TimelineEvent;
  isLast:   boolean;
  onIgnore: (id: string) => void;
  onUpload: () => void;
}> = ({ row, isLast, onIgnore, onUpload }) => (
  <div style={{ display: "flex", gap: 14, marginBottom: isLast ? 0 : 4 }}>
    {/* Dot + line */}
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 20, flexShrink: 0 }}>
      <div style={{
        width: 12, height: 12, borderRadius: "50%", marginTop: 10, flexShrink: 0,
        background: colors.yellowText, border: `2px solid ${colors.yellowText}`,
      }} />
      {!isLast && <div style={{ flex: 1, width: 2, background: colors.border, marginTop: 4, minHeight: 16 }} />}
    </div>
    {/* Card */}
    <div style={{
      flex: 1, background: colors.yellow,
      border: `1px solid ${colors.yellowBorder}`,
      borderRadius: 10, padding: "12px 16px", marginBottom: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0 }}>
          <Icon name="warn" size={14} color={colors.yellowText} />
          <div style={{ minWidth: 0 }}>
            <span style={{ fontSize: 11, color: colors.yellowText, fontFamily: typography.sans, fontWeight: 600 }}>
              {formatDate(row.event_date)}&nbsp;·&nbsp;
            </span>
            <span style={{ fontSize: 13, color: colors.yellowText, fontFamily: typography.sans }}>
              {row.description}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button size="sm" variant="outline" onClick={onUpload}>Nachreichen</Button>
          <Button size="sm" variant="ghost" onClick={() => onIgnore(row.event_id)}>Ignorieren</Button>
        </div>
      </div>
    </div>
  </div>
);

// ── TimelineCard (normale AI/User-Ereigniskarte) ──────────────────────────────

const TimelineCard: React.FC<{
  row:      TimelineEvent;
  isLast:   boolean;
  onDelete: (id: string) => void;
  onEdit:   (row: TimelineEvent) => void;
}> = ({ row, isLast, onDelete, onEdit }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const isAi = row.source_type === "ai";

  return (
    <div style={{ display: "flex", gap: 14, marginBottom: isLast ? 0 : 4 }}>
      {/* Dot + vertical line */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 20, flexShrink: 0 }}>
        <div style={{
          width: 12, height: 12, borderRadius: "50%", marginTop: 10, flexShrink: 0,
          background: isAi ? colors.teal : colors.orange,
          border: `2px solid ${isAi ? colors.teal : colors.orange}`,
        }} />
        {!isLast && <div style={{ flex: 1, width: 2, background: colors.border, marginTop: 4, minHeight: 16 }} />}
      </div>

      {/* Card */}
      <div style={{
        flex: 1, background: colors.white, borderRadius: 10,
        border: `1px solid ${colors.border}`, padding: "12px 16px",
        boxShadow: "0 1px 4px rgba(0,0,0,.05)", marginBottom: 12,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: colors.muted, fontFamily: typography.sans, fontWeight: 600 }}>
            {formatDate(row.event_date)}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Badge color={SOURCE_BADGE_COLOR[row.source_type] ?? "muted"}>
              {SOURCE_LABEL[row.source_type] ?? row.source_type}
            </Badge>
            {/* 3-dot menu */}
            <div style={{ position: "relative" }}>
              <button
                onClick={() => setMenuOpen(m => !m)}
                onBlur={() => setTimeout(() => setMenuOpen(false), 150)}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  width: 26, height: 26, borderRadius: 6,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: colors.muted, fontSize: 16, fontFamily: typography.sans,
                }}
              >
                ···
              </button>
              {menuOpen && (
                <div style={{
                  position: "absolute", right: 0, top: 28, zIndex: 10,
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
        </div>
        <p style={{ fontSize: 13, color: colors.dark, fontFamily: typography.sans, lineHeight: 1.55, margin: 0 }}>
          {row.description}
        </p>
      </div>
    </div>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────

/**
 * Step 3: Interaktive Chronologie-Ansicht (US-4.3).
 *
 * - Pollt timeline API solange status='building'
 * - Zeigt GapCards (gelb) mit Nachreichen/Ignorieren-Buttons
 * - AI-Events: Teal-Dot, 3-Punkt-Menü (Bearbeiten, Löschen)
 * - User-Events: Orange-Dot, Badge "Eigene Angabe", gleiche Optionen
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
        {/* ── Header mit Titel + Add-Button ── */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h3 style={{ ...textStyles.h3, margin: 0 }}>3. Der Rote Faden</h3>
          {!isBuilding && (
            <Button size="sm" variant="outline" onClick={() => setShowAddModal(true)}>
              <Icon name="plus" size={13} color={colors.mid} /> Ereignis hinzufügen
            </Button>
          )}
        </div>

        {error && (
          <p style={{ fontSize: 12, color: colors.redText, fontFamily: typography.sans, marginBottom: 12 }}>
            {error}
          </p>
        )}

        {/* ── Lade-Indikator ── */}
        {isBuilding && (
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
        )}

        {/* ── Vertikale Timeline ── */}
        {!isBuilding && (
          <div style={{ marginBottom: 14 }}>
            {events.length === 0 && (
              <p style={{ ...textStyles.small, color: colors.muted, padding: "16px 0", textAlign: "center" }}>
                Noch keine Ereignisse vorhanden.
              </p>
            )}

            {events.map((row, i) =>
              row.is_gap ? (
                <GapCard
                  key={row.event_id}
                  row={row}
                  isLast={i === events.length - 1}
                  onIgnore={handleDeleteEvent}
                  onUpload={onGoToUpload ?? onBack}
                />
              ) : (
                <TimelineCard
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
