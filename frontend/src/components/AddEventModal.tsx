import React, { useState } from "react";
import { colors, textStyles, typography } from "../theme/tokens";
import { Button } from "./Button";
import { timelineApi } from "../services/api";
import type { TimelineEvent } from "../types";

interface AddEventModalProps {
  caseId:  string;
  onSave:  (event: TimelineEvent) => void;
  onClose: () => void;
}

/**
 * Modal zum Hinzufügen eines manuellen Ereignisses ohne Beleg (US-4.4).
 * Setzt source_type='user' automatisch – kein Source-Selector nötig.
 */
export const AddEventModal: React.FC<AddEventModalProps> = ({ caseId, onSave, onClose }) => {
  const today = new Date().toISOString().split("T")[0];
  const [eventDate,    setEventDate]    = useState(today);
  const [description,  setDescription]  = useState("");
  const [saving,       setSaving]       = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const charsLeft = 500 - description.length;

  const handleSave = async () => {
    if (!description.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await timelineApi.addEvent(caseId, {
        event_date:  eventDate,
        description: description.trim(),
      });
      onSave(saved);
      onClose();
    } catch {
      setError("Ereignis konnte nicht gespeichert werden.");
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
          Manuelles Ereignis hinzufügen
        </p>

        {error && (
          <p style={{ fontSize: 12, color: colors.redText, fontFamily: typography.sans, marginBottom: 12 }}>
            {error}
          </p>
        )}

        <div style={{ marginBottom: 14 }}>
          <label style={{ ...textStyles.label, display: "block", marginBottom: 6 }}>Datum</label>
          <input
            type="date"
            value={eventDate}
            max={today}
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
            <span style={{ fontWeight: 400, color: colors.muted, marginLeft: 6 }}>
              ({charsLeft} Zeichen übrig)
            </span>
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            maxLength={500}
            placeholder="z. B. Telefonat mit Kundenservice, Kündigung eingereicht…"
            rows={3}
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
            {saving ? "Speichern…" : "Hinzufügen"}
          </Button>
        </div>
      </div>
    </div>
  );
};
