import { useEffect, useRef, useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Icon } from "../../../components";
import { OpponentConfirmation } from "../../../components/OpponentConfirmation";
import {
  caseAnalyzeApi, analysisApi, extractionApi,
} from "../../../services/api";
import type { AnalysisResultResponse, DocumentListItem } from "../../../services/api";
import type { ExtractionResult, ExtractionField, OpponentCategory } from "../../../types";
import { CATEGORY_FIELDS, FIELD_LABELS_MAP } from "../../../constants/categoryFields";

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — KI-Analyse & Datenschutz (FIX1)
//
// Volles Viewport-Layout, 3 Spalten:
//   Spalte 1 (240px):  Dokument-Navigator (click-to-select)
//   Spalte 2 (flex-1): Dokumentinhalt des gewählten Dokuments
//   Spalte 3 (380px):  Erkannte Daten bestätigen (Formular)
//
// Phase "ocr"       → rechts: Analyse starten
// Phase "analyzing" → rechts: Lade-Animation
// Phase "review"    → rechts: Vollständiges Formular + Sticky Footer
// ─────────────────────────────────────────────────────────────────────────────

type Phase = "ocr" | "analyzing" | "review";

interface AnalysisStepProps {
  caseId:           string;
  onNext:           () => void;
  onBack:           () => void;
  docs:             DocumentListItem[];
  selectedDoc:      DocumentListItem | null;
  onActionChange?:  (cfg: { label: string; disabled: boolean; handler: () => void }) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function splitAndHighlight(text: string, snippets: string[]): JSX.Element {
  for (const s of snippets) {
    if (!s) continue;
    const idx = text.indexOf(s);
    if (idx >= 0) {
      return (
        <>
          {text.slice(0, idx)}
          <mark style={{ background: "#d1fae5", borderRadius: 3, padding: "0 2px", fontWeight: 600 }}>
            {text.slice(idx, idx + s.length)}
          </mark>
          {text.slice(idx + s.length)}
        </>
      );
    }
  }
  return <>{text}</>;
}

// ── Column A: Document content (flex-1, fills space from CaseFlow's DocNav) ───

const DocContent = ({
  doc, snippets, phase,
}: {
  doc: DocumentListItem | null; snippets: string[]; phase: Phase;
}) => {
  const text = doc?.masked_text_preview ?? "";

  return (
    <main style={{
      flex: 1, display: "flex", flexDirection: "column",
      overflow: "hidden", borderRight: `1px solid ${colors.border}`,
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 28px", borderBottom: `1px solid ${colors.border}`,
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
            <style>{`@keyframes bounce{0%,80%,100%{transform:scale(.8);opacity:.5}40%{transform:scale(1.2);opacity:1}}`}</style>
          </div>
        )}

        {phase !== "analyzing" && !text && doc && doc.ocr_status !== "completed" && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ width: 18, height: 18, border: `2px solid ${colors.orange}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 10px" }} />
              <p style={{ ...textStyles.small, color: colors.muted }}>Dokument wird gescannt…</p>
              <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
            </div>
          </div>
        )}

        {phase !== "analyzing" && text && (
          <>
            {/* Privacy notice */}
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              background: "#F0FDF4", border: "1px solid #BBF7D0",
              borderRadius: 12, padding: "10px 14px", marginBottom: 20,
            }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>🔒</span>
              <p style={{ fontFamily: typography.sans, fontSize: 12, color: "#15803D", lineHeight: 1.5 }}>
                IBAN und E-Mail-Adressen wurden vor der KI-Analyse automatisch geschwärzt. Das Original bleibt unverändert.
              </p>
            </div>

            {/* Extracted text */}
            <div style={{
              fontFamily: "monospace", fontSize: 12, color: colors.mid,
              lineHeight: 1.9, whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {splitAndHighlight(text, snippets)}
              {text.length >= 500 && <span style={{ color: colors.muted }}> …</span>}
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

const FieldInput = ({
  field, value, onChange, docs,
}: {
  field: ExtractionField; value: string; onChange: (k: string, v: string) => void; docs: DocumentListItem[];
}) => {
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
  starting:         boolean;
  confirming:       boolean;
  canConfirm:       boolean;
  error:            string | null;
  extraction:       ExtractionResult | null;
  docs:             DocumentListItem[];
  fieldValues:      Record<string, string>;
  oppCat:           OpponentCategory;
  oppName:          string;
  reviewFields:     ExtractionField[];
  autoFields:       ExtractionField[];
  onFieldChange:    (k: string, v: string) => void;
  onOpponentChange: (cat: OpponentCategory, name: string) => void;
}

const RightPanel = ({
  phase, allOcrDone, starting: _starting, confirming, canConfirm, error,
  extraction, docs, fieldValues, oppCat: _oppCat, oppName: _oppName,
  reviewFields, autoFields,
  onFieldChange, onOpponentChange,
}: RightPanelProps) => {
  const [expandAuto, setExpandAuto] = useState(false);

  return (
    <aside style={{
      width: 380, flexShrink: 0,
      display: "flex", flexDirection: "column",
      overflow: "hidden", background: colors.white,
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 24px", borderBottom: `1px solid ${colors.border}`,
        flexShrink: 0,
      }}>
        <p style={{ fontFamily: typography.sans, fontSize: 14, fontWeight: 700, color: colors.dark }}>
          Erkannte Daten bestätigen
        </p>
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

        {/* Phase: ocr */}
        {phase === "ocr" && (
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
                <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
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
            <style>{`@keyframes bounce{0%,80%,100%{transform:scale(.8);opacity:.5}40%{transform:scale(1.2);opacity:1}}`}</style>
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
      </div>
    </aside>
  );
};

// ── Main ─────────────────────────────────────────────────────────────────────

export const AnalysisStep = ({ caseId, onNext, onBack: _onBack, docs, selectedDoc, onActionChange }: AnalysisStepProps) => {
  const [phase,       setPhase]      = useState<Phase>("ocr");
  const [extraction,  setExtraction] = useState<ExtractionResult | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [oppCat,      setOppCat]     = useState<OpponentCategory>("sonstiges");
  const [oppName,     setOppName]    = useState("");
  const [starting,    setStarting]   = useState(false);
  const [confirming,  setConfirming] = useState(false);
  const [error,       setError]      = useState<string | null>(null);
  const analysisPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // On mount: check if analysis already done
  useEffect(() => {
    extractionApi.getFields(caseId)
      .then(r => { initExtraction(r); setPhase("review"); })
      .catch(() => {
        analysisApi.result(caseId)
          .then(r => { if (r.extracted_data) { buildLegacy(r); setPhase("review"); } })
          .catch(() => {});
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const initExtraction = (r: ExtractionResult) => {
    setExtraction(r);
    const vals: Record<string, string> = {};
    for (const f of r.fields) vals[f.key] = f.value != null ? String(f.value) : "";
    setFieldValues(vals);
    setOppCat((r.opponent.category as OpponentCategory) ?? "sonstiges");
    setOppName(r.opponent.name ?? "");
  };

  const buildLegacy = (resp: AnalysisResultResponse) => {
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
  };

  const allOcrDone     = docs.length > 0 && docs.every(d => d.ocr_status === "completed" || d.ocr_status === "error");
  const fieldConfig    = CATEGORY_FIELDS[oppCat] ?? CATEGORY_FIELDS["sonstiges"];
  const visibleKeys    = new Set(Object.entries(fieldConfig).filter(([, v]) => v).map(([k]) => k));
  const relevantFields = (extraction?.fields ?? []).filter(f => visibleKeys.has(f.key));
  const reviewFields   = relevantFields.filter(f => f.needs_review);
  const autoFields     = relevantFields.filter(f => f.auto_accepted);
  const opponentReady  = oppName.trim() !== "" || !(extraction?.opponent.needs_review);
  const canConfirm     = phase === "review" && opponentReady &&
    reviewFields.every(f => (fieldValues[f.key] ?? "").trim() !== "");

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      await caseAnalyzeApi.start(caseId);
      setPhase("analyzing");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409")) { setPhase("analyzing"); }
      else setError(`Analyse konnte nicht gestartet werden: ${msg}`);
    } finally {
      setStarting(false);
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    setError(null);
    try {
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
      onNext();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Bestätigung fehlgeschlagen.");
    } finally {
      setConfirming(false);
    }
  };

  // Header-Button-State nach oben kommunizieren
  useEffect(() => {
    if (phase === "ocr") {
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
  }, [phase, allOcrDone, starting, confirming, canConfirm]); // eslint-disable-line react-hooks/exhaustive-deps

  const snippets = extraction?.fields.map(f => f.source_text_snippet).filter(Boolean) as string[] ?? [];

  return (
    // Füllt die rechte flex-1-Spalte von CaseFlow vollständig aus (2 sub-Spalten)
    <div
      className="fade-in"
      style={{ display: "flex", height: "100%", overflow: "hidden" }}
    >
      {/* ── Spalte A: Dokumentinhalt (flex-1) ── */}
      <DocContent doc={selectedDoc} snippets={snippets} phase={phase} />

      {/* ── Spalte B: Erkannte Daten (380px) ── */}
      <RightPanel
        phase={phase}
        allOcrDone={allOcrDone}
        starting={starting}
        confirming={confirming}
        canConfirm={canConfirm}
        error={error}
        extraction={extraction}
        docs={docs}
        fieldValues={fieldValues}
        oppCat={oppCat}
        oppName={oppName}
        reviewFields={reviewFields}
        autoFields={autoFields}
        onFieldChange={(k, v) => setFieldValues(p => ({ ...p, [k]: v }))}
        onOpponentChange={(cat, name) => { setOppCat(cat); setOppName(name); }}
      />
    </div>
  );
};
