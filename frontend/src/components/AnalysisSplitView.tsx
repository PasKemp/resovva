import { useState } from "react";
import { colors, textStyles, typography } from "../theme/tokens";
import { Button } from "./Button";
import { Icon }   from "./Icon";
import { OpponentConfirmation } from "./OpponentConfirmation";
import type {} from "../services/api";
import type { ExtractionResult, ExtractionField, OpponentCategory } from "../types";
import { CATEGORY_FIELDS } from "../constants/categoryFields";
import type { DocumentListItem } from "../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// AnalysisSplitView – Analyse & Bestätigung (US-9.3)
//
// Split-View: Links (60%) Dokument-Liste mit Textauszügen,
//             Rechts (40%) Bestätigungs-Panel.
// ─────────────────────────────────────────────────────────────────────────────

// ── Field labels ─────────────────────────────────────────────────────────────

const FIELD_LABELS: Record<string, { label: string; placeholder: string }> = {
  malo_id:          { label: "Marktlokations-ID (MaLo)", placeholder: "DE…" },
  meter_number:     { label: "Zählernummer",              placeholder: "Z123456…" },
  dispute_amount:   { label: "Streitbetrag (€)",          placeholder: "274.50" },
  contract_number:  { label: "Vertragsnummer",            placeholder: "VN-…" },
  insurance_number: { label: "Versicherungsnummer",       placeholder: "VS-…" },
};

// ── Left panel ────────────────────────────────────────────────────────────────

function highlightSnippet(text: string, snippets: string[]): JSX.Element {
  if (!snippets.length) return <>{text}</>;
  // Highlight the first snippet that appears in the text
  for (const snippet of snippets) {
    if (!snippet) continue;
    const idx = text.indexOf(snippet);
    if (idx >= 0) {
      return (
        <>
          {text.slice(0, idx)}
          <mark style={{ background: "#FEF3C7", borderRadius: 2, padding: "0 1px" }}>
            {text.slice(idx, idx + snippet.length)}
          </mark>
          {text.slice(idx + snippet.length)}
        </>
      );
    }
  }
  return <>{text}</>;
}

interface DocCardProps {
  doc:      DocumentListItem;
  snippets: string[];
}

const DocCard = ({ doc, snippets }: DocCardProps) => {
  const [open, setOpen] = useState(true);
  const text = doc.masked_text_preview ?? "";

  return (
    <div style={{
      border:       `1px solid ${colors.border}`,
      borderRadius: 10,
      marginBottom: 10,
      overflow:     "hidden",
    }}>
      {/* Header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width:        "100%",
          display:      "flex",
          alignItems:   "center",
          gap:          8,
          padding:      "10px 14px",
          background:   colors.white,
          border:       "none",
          cursor:       "pointer",
          textAlign:    "left",
        }}
      >
        <Icon name="file" size={14} color={colors.orange} />
        <span style={{ flex: 1, fontFamily: typography.sans, fontSize: 12, fontWeight: 600, color: colors.dark }}>
          {doc.filename}
        </span>
        <span style={{ ...textStyles.small, color: doc.ocr_status === "completed" ? colors.teal : colors.muted }}>
          {doc.ocr_status === "completed" ? "✓ Analysiert" : "⏳ Verarbeitung…"}
        </span>
        <span style={{ color: colors.muted, fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </button>

      {/* Text excerpt */}
      {open && text && (
        <div style={{
          padding:    "0 14px 14px",
          background: colors.bg,
          fontSize:   12,
          fontFamily: typography.sans,
          color:      colors.mid,
          lineHeight: 1.7,
          whiteSpace: "pre-wrap",
          wordBreak:  "break-word",
          maxHeight:  220,
          overflowY:  "auto",
        }}>
          {highlightSnippet(text, snippets)}
          {text.length >= 500 && <span style={{ color: colors.muted }}> …</span>}
        </div>
      )}

      {open && !text && doc.ocr_status !== "completed" && (
        <div style={{ padding: "10px 14px", background: colors.bg }}>
          <p style={{ ...textStyles.small, textAlign: "center" }}>Wird noch verarbeitet…</p>
        </div>
      )}
    </div>
  );
};

// ── Confirmation field row ────────────────────────────────────────────────────

interface FieldRowProps {
  field:    ExtractionField;
  onChange: (key: string, value: string) => void;
}

const FieldRow = ({ field, onChange }: FieldRowProps) => {
  const meta        = FIELD_LABELS[field.key];
  const displayVal  = field.value != null ? String(field.value) : "";
  const [val, setVal] = useState(displayVal);

  const handleChange = (v: string) => {
    setVal(v);
    onChange(field.key, v);
  };

  return (
    <div style={{ marginBottom: 14 }}>
      <p style={{ ...textStyles.small, marginBottom: 4 }}>
        {meta?.label ?? field.key}
      </p>
      <input
        value={val}
        onChange={e => handleChange(e.target.value)}
        placeholder={meta?.placeholder ?? ""}
        style={{
          width:        "100%",
          padding:      "9px 12px",
          border:       `1.5px solid ${val ? colors.teal : colors.border}`,
          borderRadius: 8,
          fontSize:     12,
          fontFamily:   typography.sans,
          color:        colors.dark,
          outline:      "none",
          background:   colors.bg,
          boxSizing:    "border-box",
        }}
      />
      {field.source_document_id && (
        <p style={{ fontSize: 10, color: colors.muted, marginTop: 2, fontFamily: typography.sans }}>
          ✓ Aus Dokument
        </p>
      )}
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────────

interface AnalysisSplitViewProps {
  caseId:      string;
  extraction:  ExtractionResult;
  docs:        DocumentListItem[];
  onConfirm:   (data: Record<string, unknown>) => Promise<void>;
  onBack:      () => void;
  confirming:  boolean;
  error:       string | null;
  isMissing:   boolean;
}

export const AnalysisSplitView = ({
  caseId: _caseId,
  extraction,
  docs,
  onConfirm,
  onBack,
  confirming,
  error,
  isMissing,
}: AnalysisSplitViewProps) => {
  const [fieldValues, setFieldValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of extraction.fields) {
      init[f.key] = f.value != null ? String(f.value) : "";
    }
    return init;
  });

  const [opponentCategory, setOpponentCategory] = useState<OpponentCategory>(
    (extraction.opponent.category as OpponentCategory) ?? "sonstiges"
  );
  const [opponentName, setOpponentName] = useState(extraction.opponent.name ?? "");
  const [expandAutoAccepted, setExpandAutoAccepted] = useState(false);

  // Category-aware: which fields to show
  const fieldConfig = CATEGORY_FIELDS[opponentCategory];
  const visibleFieldKeys = new Set(
    Object.entries(fieldConfig)
      .filter(([, visible]) => visible)
      .map(([key]) => key)
  );

  const handleFieldChange = (key: string, value: string) => {
    setFieldValues(prev => ({ ...prev, [key]: value }));
  };

  const handleOpponentChange = (cat: OpponentCategory, name: string) => {
    setOpponentCategory(cat);
    setOpponentName(name);
  };

  // Filter fields by category relevance
  const relevantFields = extraction.fields.filter(f => visibleFieldKeys.has(f.key));
  const needsReviewFields  = relevantFields.filter(f => f.needs_review && !f.field_ignored);
  const autoAcceptedFields = relevantFields.filter(f => f.auto_accepted);

  // "Weiter" active when all needs_review fields are filled or ignored
  const allReviewedFilled = needsReviewFields.every(
    f => (fieldValues[f.key] ?? "").trim() !== "" || f.field_ignored
  );
  const opponentFilled = opponentName.trim() !== "" || !extraction.opponent.needs_review;
  const canConfirm = allReviewedFilled && opponentFilled;

  // All snippets from source for highlighting
  const allSnippets = extraction.fields
    .map(f => f.source_text_snippet)
    .filter(Boolean) as string[];

  const handleSubmit = async () => {
    const data: Record<string, unknown> = {
      opponent_category: opponentCategory,
      opponent_name:     opponentName || null,
    };
    for (const key of Object.keys(fieldValues)) {
      const raw = fieldValues[key];
      if (key === "dispute_amount") {
        data[key] = raw ? parseFloat(raw) || null : null;
      } else {
        data[key] = raw || null;
      }
    }
    // Map malo_id → malo_id, meter_number → meter_number for confirm API
    await onConfirm(data);
  };

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "flex-start", width: "100%" }}>

      {/* ── Left panel: Documents (60%) ─────────────────────────────────── */}
      <div style={{ flex: "0 0 60%", minWidth: 0, overflowY: "auto", maxHeight: "80vh" }}>
        <p style={{ ...textStyles.label, marginBottom: 14 }}>
          Dokumente ({docs.length})
        </p>

        {docs.length === 0 && (
          <p style={{ ...textStyles.small, color: colors.muted }}>Keine Dokumente.</p>
        )}

        {docs.map(doc => (
          <DocCard key={doc.document_id} doc={doc} snippets={allSnippets} />
        ))}
      </div>

      {/* ── Right panel: Confirmation (40%) ─────────────────────────────── */}
      <div style={{
        flex:     "0 0 40%",
        minWidth: 0,
        position: "sticky",
        top:      0,
        background: colors.white,
        border:   `1px solid ${colors.border}`,
        borderRadius: 12,
        padding:  20,
        maxHeight: "80vh",
        overflowY: "auto",
      }}>
        <p style={{ ...textStyles.h3, marginBottom: 18, fontSize: 15 }}>
          Erkannte Daten bestätigen
        </p>

        {error && (
          <div style={{
            background: "#FEF2F2", border: `1px solid ${colors.redText}`,
            borderRadius: 8, padding: "10px 14px", marginBottom: 14,
          }}>
            <p style={{ ...textStyles.small, color: colors.redText }}>{error}</p>
          </div>
        )}

        {isMissing && (
          <div style={{
            background: "#FFF7ED", border: `1.5px solid ${colors.orange}`,
            borderRadius: 10, padding: "12px 14px", marginBottom: 16,
            display: "flex", gap: 8, alignItems: "flex-start",
          }}>
            <Icon name="warn" size={14} color={colors.orange} />
            <p style={{ fontFamily: typography.sans, fontSize: 12, color: "#92400E", margin: 0 }}>
              Kerndaten nicht gefunden – bitte manuell ausfüllen oder weiteres Dokument hochladen.
            </p>
          </div>
        )}

        {/* Streitpartei */}
        <div style={{ marginBottom: 20 }}>
          <OpponentConfirmation
            opponent={extraction.opponent}
            onChange={handleOpponentChange}
          />
        </div>

        <hr style={{ border: "none", borderTop: `1px solid ${colors.border}`, margin: "16px 0" }} />

        {/* ⚠ Bitte prüfen */}
        {needsReviewFields.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
              <span style={{
                background: "#FFF7ED", color: colors.orange,
                fontSize: 10, fontWeight: 700, fontFamily: typography.sans,
                padding: "2px 8px", borderRadius: 50, border: `1px solid ${colors.orange}`,
              }}>
                ⚠ Bitte prüfen
              </span>
            </div>
            {needsReviewFields.map(f => (
              <FieldRow key={f.key} field={f} onChange={handleFieldChange} />
            ))}
          </div>
        )}

        {/* ✓ KI-erkannt (eingeklappt) */}
        {autoAcceptedFields.length > 0 && (
          <div>
            <button
              onClick={() => setExpandAutoAccepted(e => !e)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "none", border: "none", cursor: "pointer",
                padding: "4px 0", marginBottom: 10,
              }}
            >
              <span style={{
                background: colors.tealLight, color: colors.teal,
                fontSize: 10, fontWeight: 700, fontFamily: typography.sans,
                padding: "2px 8px", borderRadius: 50, border: `1px solid ${colors.teal}`,
              }}>
                ✓ KI-erkannt
              </span>
              <span style={{ ...textStyles.small, color: colors.muted }}>
                {expandAutoAccepted ? "▲ einklappen" : "▼ anzeigen"}
              </span>
            </button>

            {expandAutoAccepted && autoAcceptedFields.map(f => (
              <FieldRow key={f.key} field={f} onChange={handleFieldChange} />
            ))}
          </div>
        )}

        <hr style={{ border: "none", borderTop: `1px solid ${colors.border}`, margin: "16px 0" }} />

        {/* Actions */}
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
          <Button variant="outline" onClick={onBack}>Zurück</Button>
          <Button
            onClick={handleSubmit}
            disabled={confirming || !canConfirm}
            size="lg"
          >
            {confirming ? "Wird gespeichert…" : (
              <>Bestätigen & weiter <Icon name="arrow" size={15} color="#fff" /></>
            )}
          </Button>
        </div>

        {!canConfirm && !confirming && (
          <p style={{ ...textStyles.small, color: colors.muted, marginTop: 8, textAlign: "center" }}>
            Bitte alle markierten Felder ausfüllen.
          </p>
        )}
      </div>
    </div>
  );
};
