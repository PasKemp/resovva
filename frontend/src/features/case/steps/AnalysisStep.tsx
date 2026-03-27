import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { colors, shadows, textStyles, typography } from "../../../theme/tokens";
import { Button, Icon } from "../../../components";
import { OpponentConfirmation } from "../../../components/OpponentConfirmation";
import {
  caseAnalyzeApi, analysisApi, extractionApi, documentsApi,
} from "../../../services/api";
import type { AnalysisResultResponse, DocumentListItem } from "../../../services/api";
import type { ExtractionResult, ExtractionField, OpponentCategory } from "../../../types";
import { CATEGORY_FIELDS, FIELD_LABELS_MAP } from "../../../constants/categoryFields";

// Session-persistenter Summary-Cache: überlebt AnalysisStep-Unmount/Remount im selben Browser-Tab.
// Key: "${caseId}:${documentId}"
const summaryCacheMap = new Map<string, string>();

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — KI-Analyse & Datenschutz
//
// Volles Viewport-Layout, 3 Spalten:
//   Spalte 1 (240px):  Dokument-Navigator (click-to-select, in CaseFlow)
//   Spalte 2 (flex-1): Dokumentinhalt des gewählten Dokuments
//   Spalte 3 (380px):  Erkannte Daten bestätigen (Formular)
//
// Phase "ocr"       → rechts: Analyse starten
// Phase "analyzing" → rechts: Lade-Animation
// Phase "review"    → rechts: Vollständiges Formular + Sticky Footer
// ─────────────────────────────────────────────────────────────────────────────

type Phase = "loading" | "ocr" | "analyzing" | "review";

interface AnalysisStepProps {
  caseId:              string;
  onNext:              () => void;
  onBack:              () => void;
  docs:                DocumentListItem[];
  selectedDoc:         DocumentListItem | null;
  onActionChange?:     (cfg: { label: string; disabled: boolean; handler: () => void }) => void;
  /** Wird aufgerufen, sobald die KI-Analyse gestartet wird (für Re-Run-Schutz). */
  onAnalysisStarted?:  () => void;
  /** Von CaseFlow inkrementiert wenn Nutzer neues Dokument hochlädt + Reset bestätigt. */
  forceRefresh?:       number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

// ── Column A: Document content (flex-1, fills space from CaseFlow's DocNav) ───

const MD_COMPONENTS: import("react-markdown").Components = {
  p:    ({ children }) => <p    style={{ fontFamily: typography.sans, fontSize: 13, color: colors.mid, lineHeight: 1.75, marginBottom: 10, marginTop: 0 }}>{children}</p>,
  h1:   ({ children }) => <h2   style={{ fontFamily: typography.sans, fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 6, marginTop: 20 }}>{children}</h2>,
  h2:   ({ children }) => <h3   style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark, marginBottom: 4, marginTop: 16 }}>{children}</h3>,
  h3:   ({ children }) => <p    style={{ fontFamily: typography.sans, fontSize: 13, fontWeight: 700, color: colors.dark, marginBottom: 2, marginTop: 12 }}>{children}</p>,
  ul:   ({ children }) => <ul   style={{ paddingLeft: 18, marginBottom: 10, marginTop: 0 }}>{children}</ul>,
  ol:   ({ children }) => <ol   style={{ paddingLeft: 18, marginBottom: 10, marginTop: 0 }}>{children}</ol>,
  li:   ({ children }) => <li   style={{ fontFamily: typography.sans, fontSize: 13, color: colors.mid, lineHeight: 1.7, marginBottom: 2 }}>{children}</li>,
  code: ({ children }) => {
    const val = String(children);
    if (val === "__MASK_IBAN__") {
      return <span style={{ background: "#DCFCE7", color: "#15803D", padding: "1px 6px", borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: "help" }} title="Zu deiner Sicherheit vor der KI verborgen">🔒 IBAN</span>;
    }
    if (val === "__MASK_EMAIL__") {
      return <span style={{ background: "#DCFCE7", color: "#15803D", padding: "1px 6px", borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: "help" }} title="Zu deiner Sicherheit vor der KI verborgen">🔒 E-Mail</span>;
    }
    return <code style={{ fontFamily: "monospace", fontSize: 11, background: colors.bg, borderRadius: 4, padding: "1px 5px", color: colors.mid }}>{children}</code>;
  },
  table: ({ children }) => (
    <div style={{ overflowX: "auto", marginBottom: 14 }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12, fontFamily: typography.sans }}>{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th style={{ background: colors.bg, borderBottom: `2px solid ${colors.border}`, padding: "6px 10px", textAlign: "left", fontWeight: 600, color: colors.dark, whiteSpace: "nowrap" }}>{children}</th>
  ),
  td: ({ children }) => (
    <td style={{ borderBottom: `1px solid ${colors.border}`, padding: "5px 10px", color: colors.mid, verticalAlign: "top" }}>{children}</td>
  ),
};

const DocContent: React.FC<{
  doc:            DocumentListItem | null;
  phase:          Phase;
  summary:        string | null;
  summaryLoading: boolean;
}> = ({ doc, phase, summary, summaryLoading }) => {
  const rawText = doc?.masked_text_preview ?? "";
  // Replace PII masking tokens with backtick-wrapped placeholders so the custom
  // code component in MD_COMPONENTS can render them as green highlighted spans.
  const text = rawText
    .replace(/\*\*\*IBAN\*\*\*/g, "`__MASK_IBAN__`")
    .replace(/\*\*\*@\*\*\*\.\*\*\*/g, "`__MASK_EMAIL__`");

  return (
    <main style={{
      flex: 1, display: "flex", flexDirection: "column",
      overflow: "hidden", borderRight: `1px solid ${colors.border}`,
    }}>
      {/* Header */}
      <div style={{
        padding: "20px 28px 14px", borderBottom: `1px solid ${colors.border}`,
        flexShrink: 0, background: colors.white,
      }}>
        <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 600, color: colors.dark, marginBottom: 2 }}>
          {doc?.filename ?? "Kein Dokument ausgewählt"}
        </p>
        {doc && (
          <p style={{ fontFamily: typography.sans, fontSize: 11, color: doc.ocr_status === "completed" ? "#27AE60" : colors.muted }}>
            {doc.ocr_status === "completed" ? "✓ Analysiert" : "⏳ Wird verarbeitet…"}
          </p>
        )}
      </div>

      {/* Scrollable content area */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>

        {phase === "analyzing" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: "50%",
              background: colors.orangeLight,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name="brain" size={24} color={colors.orange} />
            </div>
            <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark }}>
              KI analysiert Dokumente…
            </p>
            <div style={{ display: "flex", gap: 5 }}>
              {[0, 150, 300].map(d => (
                <div key={d} style={{
                  width: 8, height: 8, borderRadius: "50%", background: colors.orange,
                  animation: `bounce 1.2s ease-in-out ${d}ms infinite`,
                }} />
              ))}
            </div>
          </div>
        )}

        {phase !== "analyzing" && !text && doc && doc.ocr_status !== "completed" && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ width: 18, height: 18, border: `2px solid ${colors.orange}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 10px" }} />
              <p style={{ ...textStyles.small, color: colors.muted }}>Dokument wird gescannt…</p>
            </div>
          </div>
        )}

        {phase !== "analyzing" && text && (
          <>
            {/* KI-Zusammenfassung */}
            {summaryLoading && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                <div style={{ width: 14, height: 14, border: `2px solid ${colors.teal}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
                <span style={{ fontFamily: typography.sans, fontSize: 12, color: colors.muted }}>Zusammenfassung wird erstellt…</span>
              </div>
            )}
            {summary && (
              <div style={{
                background: colors.tealLight, border: `1px solid ${colors.teal}`,
                borderRadius: 12, padding: "12px 16px", marginBottom: 16,
              }}>
                <p style={{ fontFamily: typography.sans, fontWeight: 700, fontSize: 12, color: colors.teal, marginBottom: 8, marginTop: 0 }}>
                  ✦ KI-Zusammenfassung
                </p>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                  {summary}
                </ReactMarkdown>
              </div>
            )}

            {/* Privacy notice */}
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              background: "#F0FDF4", border: "1px solid #BBF7D0",
              borderRadius: 12, padding: "10px 14px", marginBottom: 20,
            }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>🔒</span>
              <p style={{ fontFamily: typography.sans, fontSize: 12, color: "#15803D", lineHeight: 1.5, margin: 0 }}>
                IBAN und E-Mail-Adressen wurden vor der KI-Analyse automatisch geschwärzt. Das Original bleibt unverändert.
              </p>
            </div>

            {/* Markdown-Rendering */}
            <div style={{ position: "relative" }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                {text}
              </ReactMarkdown>
              {/* Sanftes Fade-Out wenn Text gekürzt */}
              {rawText.length >= 2490 && (
                <div style={{
                  position: "absolute", bottom: 0, left: 0, right: 0, height: 64,
                  background: "linear-gradient(to bottom, transparent, #fff)",
                  pointerEvents: "none",
                }} />
              )}
            </div>
          </>
        )}

        {phase !== "analyzing" && !text && (!doc || doc.ocr_status === "completed") && (
          <p style={{ ...textStyles.small, color: colors.muted, textAlign: "center", paddingTop: 40 }}>
            Kein Textinhalt verfügbar.
          </p>
        )}
      </div>
    </main>
  );
};

// ── Column 3 right panel helpers ──────────────────────────────────────────────

const INPUT: React.CSSProperties = {
  width: "100%", padding: "9px 14px", fontSize: 13,
  fontFamily: typography.sans, color: colors.dark,
  border: `1.5px solid ${colors.border}`, borderRadius: 10,
  outline: "none", background: colors.bg, boxSizing: "border-box",
};

const FieldInput: React.FC<{
  field:    ExtractionField;
  value:    string;
  onChange: (k: string, v: string) => void;
  docs:     DocumentListItem[];
}> = ({ field, value, onChange, docs }) => {
  const meta      = FIELD_LABELS_MAP[field.key];
  const sourceDoc = field.source_document_id
    ? docs.find(d => d.document_id === field.source_document_id)
    : null;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <label style={{
          fontSize: 11, fontWeight: 600, color: colors.muted, fontFamily: typography.sans,
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          {meta?.label ?? field.key}
        </label>
        {field.confidence > 0 && (
          <span style={{ fontSize: 10, color: field.auto_accepted ? colors.teal : colors.orange, fontFamily: typography.sans }}>
            {Math.round(field.confidence * 100)}%
          </span>
        )}
      </div>
      <input
        value={value}
        onChange={e => onChange(field.key, e.target.value)}
        placeholder={meta?.placeholder ?? ""}
        style={{
          ...INPUT,
          borderColor: value ? "#BBF7D0" : field.needs_review ? "#FED7AA" : colors.border,
          background:  value ? "#F0FDF4" : field.needs_review ? "#FFF7ED" : colors.bg,
        }}
      />
      {field.source_document_id && (
        <p style={{ fontSize: 10, color: colors.teal, marginTop: 3, fontFamily: typography.sans }}>
          ✓ Aus {sourceDoc?.filename ?? "Dokument"}
        </p>
      )}
    </div>
  );
};

// ── Column 3: Right panel ─────────────────────────────────────────────────────

interface RightPanelProps {
  phase:            Phase;
  allOcrDone:       boolean;
  confirming:       boolean;
  canConfirm:       boolean;
  error:            string | null;
  extraction:       ExtractionResult | null;
  docs:             DocumentListItem[];
  fieldValues:      Record<string, string>;
  reviewFields:     ExtractionField[];
  autoFields:       ExtractionField[];
  onFieldChange:    (k: string, v: string) => void;
  onOpponentChange: (cat: OpponentCategory, name: string) => void;
  onUploadMore:     () => void;
  onRerunRequest:   () => void;
  dataPreloaded:    boolean;
  isDirty:          boolean;
}

const RightPanel: React.FC<RightPanelProps> = ({
  phase, allOcrDone, confirming, canConfirm, error,
  extraction, docs, fieldValues,
  reviewFields, autoFields,
  onFieldChange, onOpponentChange, onUploadMore, onRerunRequest,
  dataPreloaded, isDirty,
}) => {
  const [expandAuto, setExpandAuto] = useState(false);

  // US-3.3: both critical fields missing → offer to upload additional document
  const isMissingCritical = phase === "review" &&
    !(fieldValues["meter_number"] ?? "").trim() &&
    !(fieldValues["malo_id"] ?? "").trim();

  return (
    <aside style={{
      width: 380, flexShrink: 0,
      display: "flex", flexDirection: "column",
      overflow: "hidden", background: colors.white,
    }}>
      {/* Header */}
      <div style={{
        padding: "20px 24px 14px", borderBottom: `1px solid ${colors.border}`,
        flexShrink: 0,
      }}>
        <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark }}>
          Erkannte Daten bestätigen
        </p>
        {phase === "review" && dataPreloaded && !isDirty && (
          <p style={{ fontFamily: typography.sans, fontSize: 11, color: "#15803D", marginTop: 4, margin: "4px 0 0" }}>
            ✓ Daten geladen – keine neue KI-Analyse nötig
          </p>
        )}
        {phase === "review" && isDirty && (
          <p style={{ fontFamily: typography.sans, fontSize: 11, color: colors.orange, marginTop: 4, margin: "4px 0 0" }}>
            ● Änderungen werden beim Weiter gespeichert
          </p>
        )}
      </div>

      {/* Scrollable form */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

        {error && (
          <div style={{
            background: "#FEF2F2", border: `1px solid ${colors.redText}`,
            borderRadius: 8, padding: "8px 12px", marginBottom: 14,
          }}>
            <p style={{ ...textStyles.small, color: colors.redText }}>{error}</p>
          </div>
        )}

        {/* Phase: loading / ocr */}
        {(phase === "ocr" || phase === "loading") && (
          <>
            <div style={{
              background: colors.tealLight, border: `1px solid ${colors.teal}`,
              borderRadius: 10, padding: "12px 14px", marginBottom: 16,
            }}>
              <p style={{ fontFamily: typography.sans, fontSize: 12, fontWeight: 600, color: colors.teal, marginBottom: 4 }}>
                🔒 Ihre Daten sind geschützt
              </p>
              <p style={{ ...textStyles.small, color: colors.mid }}>
                Sensible Daten wie IBAN und E-Mail werden automatisch geschwärzt, bevor die KI sie verarbeitet.
              </p>
            </div>

            {!allOcrDone ? (
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", marginBottom: 12 }}>
                <div style={{
                  width: 16, height: 16, border: `2px solid ${colors.orange}`,
                  borderTopColor: "transparent", borderRadius: "50%",
                  animation: "spin 0.8s linear infinite", flexShrink: 0,
                }} />
                <p style={{ ...textStyles.small, color: colors.mid }}>Dokumente werden gescannt…</p>
              </div>
            ) : (
              <div style={{
                background: "#F0FDF4", border: "1px solid #BBF7D0",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
              }}>
                <p style={{ fontFamily: typography.sans, fontSize: 12, fontWeight: 600, color: "#15803D" }}>
                  ✅ Alle Dokumente bereit
                </p>
              </div>
            )}
          </>
        )}

        {/* Phase: analyzing */}
        {phase === "analyzing" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 0", gap: 12 }}>
            <div style={{ display: "flex", gap: 5 }}>
              {[0, 150, 300].map(d => (
                <div key={d} style={{
                  width: 8, height: 8, borderRadius: "50%", background: colors.orange,
                  animation: `bounce 1.2s ease-in-out ${d}ms infinite`,
                }} />
              ))}
            </div>
            <p style={{ ...textStyles.small, color: colors.muted }}>KI analysiert…</p>
          </div>
        )}

        {/* Phase: review */}
        {phase === "review" && extraction && (
          <>
            {/* Streitpartei */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <label style={{ ...textStyles.label }}>Streitpartei</label>
                {extraction.opponent.needs_review && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, fontFamily: typography.sans,
                    background: "#FFF7ED", color: colors.orange,
                    padding: "2px 8px", borderRadius: 50,
                  }}>
                    ⚠ Bitte prüfen
                  </span>
                )}
              </div>
              <OpponentConfirmation
                opponent={extraction.opponent}
                onChange={onOpponentChange}
              />
            </div>

            <div style={{ borderTop: `1px solid ${colors.border}`, margin: "16px 0" }} />

            {/* "Bitte prüfen" */}
            {reviewFields.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{
                  fontSize: 10, fontWeight: 700, color: colors.orange,
                  fontFamily: typography.sans, textTransform: "uppercase",
                  letterSpacing: "0.07em", marginBottom: 10,
                }}>
                  ⚠ Bitte prüfen
                </p>
                {reviewFields.map(f => (
                  <FieldInput
                    key={f.key} field={f}
                    value={fieldValues[f.key] ?? ""}
                    onChange={onFieldChange} docs={docs}
                  />
                ))}
              </div>
            )}

            {/* "KI-erkannt" eingeklappt */}
            {autoFields.length > 0 && (
              <div>
                <button
                  onClick={() => setExpandAuto(e => !e)}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    background: "none", border: "none", cursor: "pointer",
                    padding: "2px 0", marginBottom: expandAuto ? 10 : 0,
                    width: "100%", justifyContent: "space-between",
                  }}
                >
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: colors.teal,
                    fontFamily: typography.sans, textTransform: "uppercase", letterSpacing: "0.07em",
                  }}>
                    ✓ KI-erkannt ({autoFields.length} Felder)
                  </span>
                  <span style={{ fontSize: 10, color: colors.muted }}>{expandAuto ? "▲" : "▼"}</span>
                </button>
                {expandAuto && autoFields.map(f => (
                  <FieldInput
                    key={f.key} field={f}
                    value={fieldValues[f.key] ?? ""}
                    onChange={onFieldChange} docs={docs}
                  />
                ))}
              </div>
            )}
          </>
        )}
        {/* Inline warning when review fields missing */}
        {phase === "review" && !canConfirm && !confirming && reviewFields.length > 0 && (
          <p style={{ fontSize: 11, color: colors.orange, fontFamily: typography.sans, marginTop: 12 }}>
            ⚠ Bitte alle markierten Felder ausfüllen.
          </p>
        )}

        {/* US-3.3: Missing critical data → offer upload of additional document */}
        {isMissingCritical && (
          <div style={{
            background: "#FFF7ED", border: "1px solid #FED7AA",
            borderRadius: 10, padding: "12px 14px", marginTop: 16,
          }}>
            <p style={{ fontFamily: typography.sans, fontSize: 12, fontWeight: 600, color: colors.orange, marginBottom: 6 }}>
              ⚠ Wir konnten keine Zählernummer finden.
            </p>
            <p style={{ fontFamily: typography.sans, fontSize: 11, color: colors.mid, lineHeight: 1.5, marginBottom: 10 }}>
              Füge manuell eine Zählernummer oder MaLo-ID ein, oder lade ein weiteres Dokument hoch.
            </p>
            <button
              onClick={onUploadMore}
              style={{
                width: "100%", padding: "8px 12px", borderRadius: 8,
                border: `1.5px solid ${colors.orange}`, background: "transparent",
                color: colors.orange, fontFamily: typography.sans, fontSize: 12,
                fontWeight: 600, cursor: "pointer",
              }}
            >
              Weiteres Dokument hochladen
            </button>
          </div>
        )}

        {/* Analyse neu starten (nur in review-Phase) */}
        {phase === "review" && (
          <div style={{ borderTop: `1px solid ${colors.border}`, marginTop: 20, paddingTop: 16 }}>
            <button
              onClick={onRerunRequest}
              style={{
                width: "100%", padding: "8px 12px", borderRadius: 8,
                border: `1.5px solid ${colors.border}`, background: "transparent",
                color: colors.muted, fontFamily: typography.sans, fontSize: 12,
                cursor: "pointer",
              }}
            >
              ↻ Analyse neu starten
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};

// ── Main ─────────────────────────────────────────────────────────────────────

/**
 * Step 2: KI-Analyse — OCR-Ergebnis prüfen, Daten bestätigen (Human-in-the-Loop).
 */
export const AnalysisStep: React.FC<AnalysisStepProps> = ({
  caseId, onNext, onBack, docs, selectedDoc, onActionChange, onAnalysisStarted,
  forceRefresh = 0,
}) => {
  const [phase,           setPhase]          = useState<Phase>("loading");
  const [extraction,      setExtraction]      = useState<ExtractionResult | null>(null);
  const [fieldValues,     setFieldValues]     = useState<Record<string, string>>({});
  const [oppCat,          setOppCat]          = useState<OpponentCategory>("sonstiges");
  const [oppName,         setOppName]         = useState("");
  const [starting,        setStarting]        = useState(false);
  const [confirming,      setConfirming]      = useState(false);
  const confirmingRef = useRef(false); // sofortiger Lock – verhindert Race-Condition durch Mehrfachklick
  const [error,           setError]           = useState<string | null>(null);
  const [summaries,       setSummaries]       = useState<Record<string, string>>({});
  const [summaryLoading,  setSummaryLoading]  = useState<Record<string, boolean>>({});
  const [dataPreloaded,   setDataPreloaded]   = useState(false);
  const [isDirty,         setIsDirty]         = useState(false);
  const [showRerunConfirm, setShowRerunConfirm] = useState(false);
  const analysisPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const initExtraction = useCallback((r: ExtractionResult) => {
    setExtraction(r);
    const vals: Record<string, string> = {};
    for (const f of r.fields) vals[f.key] = f.value != null ? String(f.value) : "";
    setFieldValues(vals);
    setOppCat((r.opponent.category as OpponentCategory) ?? "sonstiges");
    setOppName(r.opponent.name ?? "");
  }, []);

  const buildLegacy = useCallback((resp: AnalysisResultResponse) => {
    const d = resp.extracted_data;
    if (!d) return;
    const r: ExtractionResult = {
      fields: [
        { key: "malo_id",        value: d.malo_id ?? null,        confidence: 0.6,  needs_review: !d.malo_id,        auto_accepted: !!d.malo_id,        source_document_id: null, source_text_snippet: null, field_ignored: false },
        { key: "meter_number",   value: d.meter_number ?? null,   confidence: 0.6,  needs_review: !d.meter_number,   auto_accepted: !!d.meter_number,   source_document_id: null, source_text_snippet: null, field_ignored: false },
        { key: "dispute_amount", value: d.dispute_amount ?? null, confidence: 0.85, needs_review: false,             auto_accepted: !!d.dispute_amount, source_document_id: null, source_text_snippet: null, field_ignored: false },
      ],
      opponent: {
        category:     (d.opponent_category as OpponentCategory | null) ?? null,
        name:         d.opponent_name ?? d.network_operator ?? null,
        confidence:   0.5,
        needs_review: true,
      },
    };
    initExtraction(r);
  }, [initExtraction]);

  // Zusammenfassungen im Hintergrund für ALLE Dokumente laden (modul-level Cache verhindert Re-Requests bei Remount)
  useEffect(() => {
    docs.forEach(doc => {
      if (!doc.masked_text_preview || doc.masked_text_preview.length < 600) return;
      const id  = doc.document_id;
      const key = `${caseId}:${id}`;

      // Bereits im Modul-Cache? → direkt setzen, kein API-Call
      if (summaryCacheMap.has(key)) {
        setSummaries(prev => ({ ...prev, [id]: summaryCacheMap.get(key)! }));
        return;
      }

      // Bereits lädt in diesem Mount-Zyklus?
      if (summaryLoading[id]) return;

      setSummaryLoading(prev => ({ ...prev, [id]: true }));
      documentsApi.summarize(caseId, id)
        .then(r => {
          const text = r.summary ?? "";
          summaryCacheMap.set(key, text);
          setSummaries(prev => ({ ...prev, [id]: text }));
        })
        .catch(() => { summaryCacheMap.set(key, ""); }) // Fehler cachen um Retry-Loop zu verhindern
        .finally(() => setSummaryLoading(prev => ({ ...prev, [id]: false })));
    });
  }, [caseId, docs]); // summaryLoading bewusst nicht in Deps → verhindert Feedback-Loop

  // On mount: check if analysis already done (restore "review" without re-running)
  // forceRefresh > 0 signalisiert: neue Dokumente hochgeladen → Cache invalidieren, zurück zu "ocr"
  useEffect(() => {
    if (forceRefresh > 0) {
      for (const key of summaryCacheMap.keys()) {
        if (key.startsWith(`${caseId}:`)) summaryCacheMap.delete(key);
      }
      setSummaries({});
      setSummaryLoading({});
      setExtraction(null);
      setFieldValues({});
      setDataPreloaded(false);
      setIsDirty(false);
      setPhase("ocr");
      return;
    }

    extractionApi.getFields(caseId)
      .then(r => {
        initExtraction(r);
        setDataPreloaded(true);
        setIsDirty(false);
        setPhase("review");
      })
      .catch(() => {
        analysisApi.result(caseId)
          .then(r => {
            if (r.extracted_data) {
              buildLegacy(r);
              setDataPreloaded(true);
              setIsDirty(false);
              setPhase("review");
            } else {
              setDataPreloaded(false);
              setPhase("ocr");
            }
          })
          .catch(() => { setDataPreloaded(false); setPhase("ocr"); });
      });
  }, [caseId, forceRefresh, initExtraction, buildLegacy]);

  // Poll for analysis result
  useEffect(() => {
    if (phase !== "analyzing") return;
    analysisPollRef.current = setInterval(async () => {
      try {
        const r = await extractionApi.getFields(caseId);
        initExtraction(r);
        setPhase("review");
        clearInterval(analysisPollRef.current!);
      } catch {
        analysisApi.result(caseId).then(r => {
          if (r.status === "error") {
            setError("Analyse fehlgeschlagen. Bitte Seite neu laden.");
            clearInterval(analysisPollRef.current!);
          } else if (r.extracted_data) {
            buildLegacy(r);
            setPhase("review");
            clearInterval(analysisPollRef.current!);
          }
        }).catch(() => {});
      }
    }, 2500);
    return () => { if (analysisPollRef.current) clearInterval(analysisPollRef.current); };
  }, [phase, caseId, initExtraction, buildLegacy]);

  const allOcrDone     = docs.length > 0 && docs.every(d => d.ocr_status === "completed" || d.ocr_status === "error");
  const fieldConfig    = CATEGORY_FIELDS[oppCat] ?? CATEGORY_FIELDS["sonstiges"];
  const visibleKeys    = new Set(Object.entries(fieldConfig).filter(([, v]) => v).map(([k]) => k));
  const relevantFields = (extraction?.fields ?? []).filter(f => visibleKeys.has(f.key));
  const reviewFields   = relevantFields.filter(f => f.needs_review);
  const autoFields     = relevantFields.filter(f => f.auto_accepted);
  const opponentReady  = oppName.trim() !== "" || !(extraction?.opponent.needs_review);
  const canConfirm     = phase === "review" && opponentReady &&
    reviewFields.every(f => (fieldValues[f.key] ?? "").trim() !== "");

  const handleStart = useCallback(async (options?: { force?: boolean }) => {
    const isForced = options?.force ?? false;

    // Defensiver Pre-Check (nur bei normalem Start, nicht bei explizitem Re-Run):
    // Falls Extraktionsdaten bereits vorhanden sind, direkt zur Review-Phase wechseln
    // ohne POST /analyze aufzurufen. Verhindert versehentliche Doppel-Analysen.
    if (!isForced) {
      try {
        const existing = await extractionApi.getFields(caseId);
        initExtraction(existing);
        setDataPreloaded(true);
        setIsDirty(false);
        setPhase("review");
        onAnalysisStarted?.();
        return;
      } catch {
        // 404 → Daten existieren noch nicht → normal fortfahren mit POST /analyze
      }
    }

    setStarting(true);
    setError(null);
    try {
      await caseAnalyzeApi.start(caseId, isForced);
      setPhase("analyzing");
      onAnalysisStarted?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409")) {
        // 409 kann bedeuten: OCR noch in Arbeit ODER Analyse bereits abgeschlossen
        // → versuche vorhandene Daten zu laden bevor wir Polling starten
        try {
          const existing = await extractionApi.getFields(caseId);
          initExtraction(existing);
          setDataPreloaded(true);
          setIsDirty(false);
          setPhase("review");
          onAnalysisStarted?.();
        } catch {
          // Daten noch nicht da (OCR läuft noch) → polling starten
          setPhase("analyzing");
          onAnalysisStarted?.();
        }
      } else {
        setError(`Analyse konnte nicht gestartet werden: ${msg}`);
      }
    } finally {
      setStarting(false);
    }
  }, [caseId, onAnalysisStarted, initExtraction]);

  const handleConfirm = useCallback(async () => {
    if (confirmingRef.current) return; // sofortiger Lock gegen Mehrfachklick
    confirmingRef.current = true;
    setConfirming(true);
    setError(null);
    try {
      // GUARD: Daten vom Server geladen + Nutzer hat nichts geändert → direkt weiter, kein API-Call
      if (dataPreloaded && !isDirty) {
        confirmingRef.current = false;
        onNext();
        return;
      }

      const data: Record<string, unknown> = { opponent_category: oppCat, opponent_name: oppName || null };
      for (const [k, v] of Object.entries(fieldValues)) {
        data[k] = k === "dispute_amount" ? (v ? parseFloat(v) || null : null) : (v || null);
      }
      await analysisApi.confirm(caseId, {
        malo_id:           data.malo_id as string | null,
        meter_number:      data.meter_number as string | null,
        dispute_amount:    data.dispute_amount as number | null,
        network_operator:  oppName || null,
        opponent_category: oppCat,
        opponent_name:     oppName || null,
      });
      setDataPreloaded(true);
      setIsDirty(false);
      onNext();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);

      // Fehler 409 bedeutet, dass der Status serverseitig bereits fortgeschritten ist
      // (z.B. user ist zurückgesprungen und klickt erneut auf "Bestätigen").
      // In diesem Fall dürfen wir den User einfach weiterlassen, ohne die Analyse neu zu erzwingen!
      if (msg.includes("409")) {
        confirmingRef.current = false;
        setDataPreloaded(true);
        setIsDirty(false);
        onNext();
        return;
      }

      confirmingRef.current = false; // Lock freigeben damit Nutzer es erneut versuchen kann
      setError(msg || "Bestätigung fehlgeschlagen.");
    } finally {
      setConfirming(false);
    }
  }, [caseId, oppCat, oppName, fieldValues, onNext, dataPreloaded, isDirty]);

  // Header-Button-State nach oben kommunizieren
  useEffect(() => {
    if (phase === "loading") {
      onActionChange?.({ label: "Wird geladen…", disabled: true, handler: () => {} });
    } else if (phase === "ocr") {
      onActionChange?.({
        label:    starting ? "Wird gestartet…" : "KI-Analyse starten",
        disabled: !allOcrDone || starting,
        handler:  handleStart,
      });
    } else if (phase === "analyzing") {
      onActionChange?.({ label: "KI analysiert…", disabled: true, handler: () => {} });
    } else {
      onActionChange?.({
        label:    confirming ? "Wird gespeichert…" : "Bestätigen & weiter",
        disabled: !canConfirm || confirming,
        handler:  handleConfirm,
      });
    }
  }, [phase, allOcrDone, starting, confirming, canConfirm, handleStart, handleConfirm, onActionChange]);

  const currentSummary = selectedDoc ? (summaries[selectedDoc.document_id] ?? null) : null;
  const currentSummaryLoading = selectedDoc ? (summaryLoading[selectedDoc.document_id] ?? false) : false;

  return (
    <>
    {/* Bestätigungsdialog: Analyse neu starten */}
    {showRerunConfirm && (
      <div
        style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.4)", display: "flex", alignItems: "center", justifyContent: "center" }}
        onClick={() => setShowRerunConfirm(false)}
      >
        <div onClick={e => e.stopPropagation()} style={{ background: colors.white, borderRadius: 16, padding: 28, width: 400, boxShadow: shadows.modal }}>
          <p style={{ fontFamily: typography.sans, fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 12 }}>
            Analyse neu starten?
          </p>
          <p style={{ fontFamily: typography.sans, fontSize: 14, color: colors.mid, lineHeight: 1.6, marginBottom: 24 }}>
            Die bisherigen KI-Ergebnisse werden verworfen und eine neue Analyse gestartet. Dies verursacht zusätzliche Kosten.
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <Button variant="outline" onClick={() => setShowRerunConfirm(false)}>Abbrechen</Button>
            <Button onClick={() => { setShowRerunConfirm(false); handleStart({ force: true }); }}>Ja, neu analysieren</Button>
          </div>
        </div>
      </div>
    )}

    <div
      className="fade-in"
      style={{
        flex: 1,
        minHeight: 0,
        width: "100%",
        display: "flex",
        flexDirection: "row",
        background: colors.white,
        borderRadius: 14,
        border: `1px solid ${colors.border}`,
        boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
        overflow: "hidden",
      }}
    >
      {/* ── Spalte A: Dokumentinhalt (flex-1) ── */}
      <DocContent doc={selectedDoc} phase={phase} summary={currentSummary} summaryLoading={currentSummaryLoading} />

      {/* ── Spalte B: Erkannte Daten (380px) ── */}
      <RightPanel
        phase={phase}
        allOcrDone={allOcrDone}
        confirming={confirming}
        canConfirm={canConfirm}
        error={error}
        extraction={extraction}
        docs={docs}
        fieldValues={fieldValues}
        reviewFields={reviewFields}
        autoFields={autoFields}
        onFieldChange={(k, v) => { setFieldValues(p => ({ ...p, [k]: v })); setIsDirty(true); }}
        onOpponentChange={(cat, name) => { setOppCat(cat); setOppName(name); setIsDirty(true); }}
        onUploadMore={onBack}
        onRerunRequest={() => setShowRerunConfirm(true)}
        dataPreloaded={dataPreloaded}
        isDirty={isDirty}
      />
    </div>
    </>
  );
};
