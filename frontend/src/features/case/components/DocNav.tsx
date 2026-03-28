import React from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Icon } from "../../../components";
import type { DocumentListItem } from "../../../services/api";

interface DocNavProps {
  docs: DocumentListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  open: boolean;
  onToggle: () => void;
}

export const DocNav: React.FC<DocNavProps> = ({
  docs, selectedId, onSelect, open, onToggle,
}) => (
  <aside style={{
    width: open ? 240 : 36, flexShrink: 0,
    borderRight: `1px solid ${colors.border}`,
    display: "flex", flexDirection: "column",
    background: colors.bg,
    transition: "width .22s ease",
    overflow: "hidden",
  }}>
    <div style={{
      padding: "12px 10px", flexShrink: 0,
      display: "flex", alignItems: "center",
      justifyContent: open ? "space-between" : "center",
      borderBottom: `1px solid ${colors.border}`,
    }}>
      {open && <p style={{ ...textStyles.label, margin: 0 }}>Dokumente ({docs.length})</p>}
      <button
        onClick={onToggle}
        title={open ? "Seitenleiste einklappen" : "Seitenleiste ausklappen"}
        style={{
          background: "none", border: "none", cursor: "pointer",
          width: 24, height: 24, borderRadius: 6, flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: colors.muted, fontSize: 18, fontFamily: typography.sans,
        }}
      >
        {open ? "‹" : "›"}
      </button>
    </div>

    {open && docs.length === 0 && (
      <p style={{ ...textStyles.small, color: colors.muted, padding: "12px 20px" }}>
        Noch keine Dokumente
      </p>
    )}

    {open && docs.map(doc => {
      const active = doc.document_id === selectedId;
      const done   = doc.ocr_status === "completed";
      const err    = doc.ocr_status === "error";
      return (
        <button
          key={doc.document_id}
          onClick={() => onSelect(doc.document_id)}
          style={{
            width: "100%", textAlign: "left",
            padding: "12px 20px",
            borderTop: "none", borderRight: "none",
            borderBottom: `1px solid ${colors.border}`,
            borderLeft: `3px solid ${active ? colors.orange : "transparent"}`,
            background: active ? colors.white : "transparent",
            cursor: "pointer", transition: "background .15s",
          }}
          onMouseEnter={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = colors.white; }}
          onMouseLeave={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <div style={{
              width: 28, height: 28, flexShrink: 0, marginTop: 1,
              background: colors.orangeLight, borderRadius: 6,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name="file" size={13} color={colors.orange} />
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{
                fontFamily: typography.sans, fontSize: 12, fontWeight: 600, color: colors.dark,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                lineHeight: 1.3, marginBottom: 3,
              }}>
                {doc.filename}
              </p>
              <p style={{
                fontFamily: typography.sans, fontSize: 11,
                color: done ? "#27AE60" : err ? colors.redText : colors.orange,
              }}>
                {done ? "✓ Analysiert"
                  : err  ? "✗ Fehler"
                  : doc.ocr_status === "masking"              ? "⏳ Maskierung…"
                  : doc.ocr_status === "llama_parse_fallback" ? "⏳ Cloud-Analyse…"
                  : doc.ocr_status === "parsing"              ? "⏳ Extraktion…"
                  : "⏳ Verarbeitung…"}
              </p>
            </div>
          </div>
        </button>
      );
    })}
  </aside>
);
