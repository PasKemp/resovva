import { useEffect, useRef, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import { UploadStep } from "./steps/UploadStep";
import { AnalysisStep } from "./steps/AnalysisStep";
import { TimelineStep } from "./steps/TimelineStep";
import { CheckoutStep } from "./steps/CheckoutStep";
import { casesApi, caseStatusApi } from "../../services/api";
import type { DocumentListItem } from "../../services/api";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// CaseFlow — Konsistentes Full-Width-Layout über alle 4 Schritte:
//
//  ┌──────────────┬──────────────────────────────────────────────────────┐
//  │ DOC-NAV      │  SCHRITT-INHALT                                      │
//  │ 240px fix    │  flex-1 (wächst mit dem Viewport)                    │
//  │  (immer      │                                                      │
//  │   sichtbar)  │  Step 1: Upload-Formular                             │
//  │              │  Step 2: [Dokument-Text flex-1] | [Form 380px]       │
//  │              │  Step 3: Timeline                                    │
//  │              │  Step 4: Checkout                                    │
//  └──────────────┴──────────────────────────────────────────────────────┘
// ─────────────────────────────────────────────────────────────────────────────

type StepIndex = 0 | 1 | 2 | 3;

interface StepMeta { label: string; sublabel: string; icon: string; }

const STEPS: StepMeta[] = [
  { label: "Upload",      sublabel: "Dokumente & Scan",    icon: "upload" },
  { label: "Analyse",     sublabel: "KI & Datenschutz",    icon: "brain"  },
  { label: "Roter Faden", sublabel: "Chronologie",         icon: "list"   },
  { label: "Abschluss",   sublabel: "Überblick & Zahlung", icon: "folder" },
];

// ── Stepper ───────────────────────────────────────────────────────────────────

const StepDot = ({ index, current }: { index: number; current: number }) => {
  const done   = index < current;
  const active = index === current;
  return (
    <div style={{
      width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
      background: done ? "#27AE60" : active ? colors.orange : colors.bg,
      border: `2px solid ${done ? "#27AE60" : active ? colors.orange : colors.border}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      transition: "all .3s ease",
    }}>
      {done
        ? <Icon name="check" size={16} color="#fff" />
        : <span style={{ fontSize: 13, fontWeight: 700, fontFamily: typography.sans, color: active ? "#fff" : colors.muted }}>
            {index + 1}
          </span>
      }
    </div>
  );
};

const Stepper = ({ current, onStep }: { current: StepIndex; onStep: (i: StepIndex) => void }) => (
  <div style={{
    background: colors.white, borderRadius: 14,
    border: `1px solid ${colors.border}`,
    padding: "16px 28px", marginBottom: 0,
    display: "flex", alignItems: "center", minHeight: 72,
  }}>
    {STEPS.map((step, i) => (
      <div key={i} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : "0 0 auto" }}>
        <div
          onClick={() => onStep(i as StepIndex)}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            cursor: i <= current ? "pointer" : "default",
            flexShrink: 0, opacity: i > current ? 0.5 : 1, transition: "opacity .2s",
          }}
        >
          <StepDot index={i} current={current} />
          <div style={{ overflow: "hidden" }}>
            <p style={{
              fontSize: 13, fontWeight: 700, fontFamily: typography.sans, lineHeight: 1.2, whiteSpace: "nowrap",
              color: i < current ? "#27AE60" : i === current ? colors.orange : colors.muted,
            }}>
              {step.label}
            </p>
            <p style={{
              fontSize: 11, fontFamily: typography.sans, lineHeight: 1.3, whiteSpace: "nowrap",
              color: i === current ? colors.mid : colors.muted,
              fontWeight: i === current ? 500 : 400,
            }}>
              {step.sublabel}
            </p>
          </div>
        </div>
        {i < STEPS.length - 1 && (
          <div style={{
            flex: 1, height: 2, minWidth: 16, margin: "0 12px", borderRadius: 2,
            background: i < current ? "#27AE60" : "#E5E7EB",
            transition: "background .4s ease",
          }} />
        )}
      </div>
    ))}
  </div>
);

// ── Persistente Dokument-Navigation (linke Spalte, immer sichtbar) ────────────

const DocNav = ({
  docs, selectedId, onSelect,
}: {
  docs: DocumentListItem[]; selectedId: string | null; onSelect: (id: string) => void;
}) => (
  <aside style={{
    width: 240, flexShrink: 0,
    borderRight: `1px solid ${colors.border}`,
    display: "flex", flexDirection: "column",
    background: colors.bg, overflowY: "auto",
  }}>
    <div style={{ padding: "16px 20px 10px", flexShrink: 0 }}>
      <p style={textStyles.label}>Dokumente ({docs.length})</p>
    </div>

    {docs.length === 0 && (
      <p style={{ ...textStyles.small, color: colors.muted, padding: "12px 20px" }}>
        Noch keine Dokumente
      </p>
    )}

    {docs.map(doc => {
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
                  : doc.ocr_status === "masking"            ? "⏳ Maskierung…"
                  : doc.ocr_status === "llama_parse_fallback" ? "⏳ Cloud-Analyse…"
                  : doc.ocr_status === "parsing"            ? "⏳ Extraktion…"
                  : "⏳ Verarbeitung…"}
              </p>
            </div>
          </div>
        </button>
      );
    })}
  </aside>
);

// ── CaseFlow ─────────────────────────────────────────────────────────────────

interface CaseFlowProps extends WithSetPage {
  caseId?:        string;
  initialStep?:   number;
  onStepChange?:  (step: number) => void;
  onCaseCreated?: (caseId: string) => void;
}

export const CaseFlow = ({
  setPage,
  caseId: initialCaseId,
  initialStep = 0,
  onStepChange,
  onCaseCreated,
}: CaseFlowProps) => {
  const [step,          setStep]          = useState<StepIndex>((initialStep as StepIndex) ?? 0);
  const [caseId,        setCaseId]        = useState<string | null>(initialCaseId ?? null);
  const [caseError,     setCaseError]     = useState<string | null>(null);
  const [docs,          setDocs]          = useState<DocumentListItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [uploadHasFiles, setUploadHasFiles] = useState(false);
  const [step1Btn, setStep1Btn] = useState<{ label: string; disabled: boolean }>({
    label: "KI-Analyse starten", disabled: true,
  });
  const step1ActionRef = useRef<() => void>(() => {});
  const hasCreatedRef = useRef(false);

  // "Weiter" aktiv: Step 0 nur wenn Dateien vorhanden, Step 2 immer
  const canNext = step === 0 ? uploadHasFiles : step === 2;
  const showNext = step === 0 || step === 2;
  const showBack = step > 0;

  // Step-Änderungen melden
  useEffect(() => { onStepChange?.(step); }, [step, onStepChange]);

  // Fall anlegen (StrictMode-Guard: leeres Array ist bewusst — einmaliger Mount-Effekt)
  useEffect(() => {
    if (caseId || hasCreatedRef.current) return;
    hasCreatedRef.current = true;
    casesApi.create()
      .then(r => { setCaseId(r.case_id); onCaseCreated?.(r.case_id); })
      .catch(() => { hasCreatedRef.current = false; setCaseError("Fall konnte nicht erstellt werden. Bitte Seite neu laden."); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- einmaliger Mount-Effekt, kein StrictMode-Problem durch Ref-Guard

  // Dokumente zentral pollen – alle Steps nutzen diese Liste
  useEffect(() => {
    if (!caseId) return;
    const load = () =>
      caseStatusApi.listDocuments(caseId)
        .then(r => setDocs(r.documents))
        .catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [caseId]);

  // Erstes Dokument automatisch selektieren
  useEffect(() => {
    if (docs.length > 0 && !selectedDocId) setSelectedDocId(docs[0].document_id);
  }, [docs, selectedDocId]);

  const goTo = (i: StepIndex) => { if (i <= step) setStep(i); };
  const next = () => setStep(s => Math.min(s + 1, 3) as StepIndex);
  const back = () => setStep(s => Math.max(s - 1, 0) as StepIndex);

  const selectedDoc = docs.find(d => d.document_id === selectedDocId) ?? docs[0] ?? null;

  if (caseError) return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <p style={{ ...textStyles.body, color: colors.redText }}>{caseError}</p>
    </div>
  );

  if (!caseId) return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <p style={{ ...textStyles.body, color: colors.muted }}>Fall wird vorbereitet…</p>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>

      {/* ── Oberer Bereich: Zurück zur Übersicht + Stepper + Nav-Buttons ── */}
      <div style={{ padding: "10px 20px 10px", flexShrink: 0, background: colors.white, borderBottom: `1px solid ${colors.border}` }}>

        {/* Zurück zur Übersicht */}
        <button
          onClick={() => setPage("dashboard")}
          style={{
            background: "none", border: "none", cursor: "pointer",
            display: "inline-flex", alignItems: "center", gap: 6,
            fontFamily: "inherit", fontSize: 12, color: colors.muted,
            padding: "0 0 8px 0",
          }}
        >
          ← Übersicht
        </button>

        {/* Stepper */}
        <Stepper current={step} onStep={goTo} />

        {/* Nav-Buttons: Zurück links, Weiter rechts */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
          <div>
            {showBack && (
              <Button variant="outline" size="sm" onClick={back}>
                ← Zurück
              </Button>
            )}
          </div>
          <div>
            {showNext && (
              <Button size="sm" onClick={next} disabled={!canNext}>
                Weiter <Icon name="arrow" size={13} color="#fff" />
              </Button>
            )}
            {step === 1 && (
              <Button size="sm" onClick={() => step1ActionRef.current()} disabled={step1Btn.disabled}>
                {step1Btn.label}
                {!step1Btn.disabled && <Icon name="arrow" size={13} color="#fff" />}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* ── Haupt-Bereich: DocNav links | Step-Inhalt rechts ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Persistente linke Spalte */}
        <DocNav docs={docs} selectedId={selectedDocId} onSelect={setSelectedDocId} />

        {/* Rechte Spalte: Step-Inhalt */}
        <div style={{
          flex: 1, minWidth: 0,
          // Step 1 (Analyse): overflow hidden, da AnalysisStep selbst 2 scrollende Spalten hat
          overflowY: step === 1 ? "hidden" : "auto",
          padding: step === 1 ? 0 : "28px 32px 48px",
          background: step === 1 ? colors.white : colors.bg,
        }}>
          {step === 0 && <UploadStep caseId={caseId} docs={docs} onNext={next} onCanNextChange={setUploadHasFiles} />}
          {step === 1 && (
            <AnalysisStep
              caseId={caseId}
              onNext={next}
              onBack={back}
              docs={docs}
              selectedDoc={selectedDoc}
              onActionChange={cfg => {
                step1ActionRef.current = cfg.handler;
                setStep1Btn({ label: cfg.label, disabled: cfg.disabled });
              }}
            />
          )}
          {step === 2 && <TimelineStep caseId={caseId} onNext={next} onBack={back} onGoToUpload={() => setStep(0)} />}
          {step === 3 && <CheckoutStep caseId={caseId} onBack={back} setPage={setPage} />}
        </div>
      </div>
    </div>
  );
};
