import React from "react";
import { colors, shadows, typography } from "../../../theme/tokens";
import { Button } from "../../../components";

interface ResetWarningDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export const ResetWarningDialog: React.FC<ResetWarningDialogProps> = ({ onConfirm, onCancel }) => (
  <div
    style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.4)", display: "flex", alignItems: "center", justifyContent: "center" }}
    onClick={onCancel}
  >
    <div
      onClick={e => e.stopPropagation()}
      style={{ background: colors.white, borderRadius: 16, padding: 28, width: 420, boxShadow: shadows.modal }}
    >
      <p style={{ fontFamily: typography.sans, fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 12 }}>
        ⚠ Fortschritt wird zurückgesetzt
      </p>
      <p style={{ fontFamily: typography.sans, fontSize: 14, color: colors.mid, lineHeight: 1.6, marginBottom: 24 }}>
        Wenn du ein neues Dokument hinzufügst, muss die KI die Chronologie neu aufbauen.
        Dein bisheriger Fortschritt in den nächsten Schritten wird zurückgesetzt. Fortfahren?
      </p>
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <Button variant="outline" onClick={onCancel}>Abbrechen</Button>
        <Button onClick={onConfirm}>Ja, fortfahren</Button>
      </div>
    </div>
  </div>
);
