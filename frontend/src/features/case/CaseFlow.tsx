import { useEffect, useRef, useState } from "react";
import { colors, shadows, textStyles, typography } from "../../theme/tokens";
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
//  │  (einklappb.)│                                                      │
//  │              │  Step 1: Upload-Formular                             │
//  │              │  Step 2: [Dokument-Text flex-1] | [Form 380px]       │
//  │              │  Step 3: Timeline                                    │
//  │              │  Step 4: Checkout                                    │
//  └──────────────┴──────────────────────────────────────────────────────┘
//  └──────────────────── Sticky Footer: Zurück / Weiter ────────────────┘
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

// ── Persistente Dokument-Navigation (linke Spalte, einklappbar) ───────────────

const DocNav = ({
  docs, selectedId, onSelect, open, onToggle,
}: {
  docs: DocumentListItem[]; selectedId: string | null; onSelect: (id: string) => void;
  open: boolean; onToggle: () => void;
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

// ── Warnung: Analyse-Reset ────────────────────────────────────────────────────

const ResetWarningDialog: React.FC<{ onConfirm: () => void; onCancel: () => void }> = ({ onConfirm, onCancel }) => (
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
  const [step,            setStep]            = useState<StepIndex>((initialStep as StepIndex) ?? 0);
  const [caseId,          setCaseId]          = useState<string | null>(initialCaseId ?? null);
  const [caseError,       setCaseError]       = useState<string | null>(null);
  const [docs,            setDocs]            = useState<DocumentListItem[]>([]);
  const [selectedDocId,   setSelectedDocId]   = useState<string | null>(null);
  const [uploadHasFiles,  setUploadHasFiles]  = useState(false);
  const [step1Btn,        setStep1Btn]        = useState<{ label: string; disabled: boolean }>({
    label: "KI-Analyse starten", disabled: true,
  });
  const [sidebarOpen,     setSidebarOpen]     = useState(true);
  const [analysisStarted, setAnalysisStarted] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [forceRefresh,    setForceRefresh]    = useState(0);

  const step1ActionRef  = useRef<() => void>(() => {});
  const hasCreatedRef   = useRef(false);
  const resolveResetRef = useRef<((v: boolean) => void) | null>(null);

  // "Weiter" aktiv: Step 0 nur wenn Dateien vorhanden, Step 2 immer
  const canNext  = step === 0 ? uploadHasFiles : step === 2;
  const showNext = step === 0 || step === 2;
  const showBack = step > 0;

  // Step-Änderungen melden
  useEffect(() => { onStepChange?.(step); }, [step, onStepChange]);

  // Sidebar automatisch einklappen wenn Schritt > 0
  useEffect(() => { setSidebarOpen(step === 0); }, [step]);

  // Fall anlegen (StrictMode-Guard: leeres Array ist bewusst — einmaliger Mount-Effekt)
  useEffect(() => {
    if (caseId || hasCreatedRef.current) return;
    hasCreatedRef.current = true;
    casesApi.create()
      .then(r => { setCaseId(r.case_id); onCaseCreated?.(r.case_id); })
      .catch(() => { hasCreatedRef.current = false; setCaseError("Fall konnte nicht erstellt werden. Bitte Seite neu laden."); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- einmaliger Mount-Effekt, kein StrictMode-Problem durch Ref-Guard

  // Vermeidung von unnötigem API-Polling über Refs (verhindert ständige Re-Render des Intervals)
  const stepRef = useRef(step);
  useEffect(() => { stepRef.current = step; }, [step]);

  const docsRef = useRef(docs);
  useEffect(() => { docsRef.current = docs; }, [docs]);

  // Dokumente zentral pollen – alle Steps nutzen diese Liste
  useEffect(() => {
    if (!caseId) return;
    const load = () =>
      caseStatusApi.listDocuments(caseId)
        .then(r => setDocs(r.documents))
        .catch(() => {});
    
    load(); // Immer sofort laden
    
    const t = setInterval(() => {
      const hasPending = docsRef.current.some(d => d.ocr_status !== "completed" && d.ocr_status !== "error");
      // Nur API aufrufen, wenn wir im Upload-Step (0) sind ODER Dokumente gerade noch verarbeitet werden
      if (stepRef.current === 0 || hasPending) {
        load();
      }
    }, 2000);
    
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

  // Promise-basierter Upload-Guard: zeigt Dialog wenn KI bereits gestartet
  const handleBeforeUpload = (): Promise<boolean> => {
    if (!analysisStarted) return Promise.resolve(true);
    return new Promise(resolve => {
      resolveResetRef.current = resolve;
      setShowResetDialog(true);
    });
  };

  const confirmReset = () => {
    setShowResetDialog(false);
    setAnalysisStarted(false);
    setForceRefresh(n => n + 1); // Signalisiert AnalysisStep: Cache invalidieren, zurück zu "ocr"
    resolveResetRef.current?.(true);
    resolveResetRef.current = null;
  };

  const cancelReset = () => {
    setShowResetDialog(false);
    resolveResetRef.current?.(false);
    resolveResetRef.current = null;
  };

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
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {showResetDialog && (
        <ResetWarningDialog onConfirm={confirmReset} onCancel={cancelReset} />
      )}

      {/* ── Oberer Bereich: Zurück zur Übersicht + Stepper ── */}
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
      </div>

      {/* ── Haupt-Bereich: DocNav links | Step-Inhalt rechts ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Einklappbare linke Spalte */}
        <DocNav
          docs={docs}
          selectedId={selectedDocId}
          onSelect={setSelectedDocId}
          open={sidebarOpen}
          onToggle={() => setSidebarOpen(o => !o)}
        />

        {/* Rechte Spalte: Step-Inhalt */}
        <div style={{
          flex: 1, minWidth: 0,
          display: "flex", flexDirection: "column",
          // Step 1 (Analyse): overflow hidden, da AnalysisStep selbst 2 scrollende Spalten hat
          overflowY: step === 1 ? "hidden" : "auto",
          
          // 🛑 FIX 1: Einheitliches Padding für ALLE Steps!
          padding: "24px 32px", 
          
          background: colors.bg,
        }}>
          {step === 0 && (
            <UploadStep
              caseId={caseId}
              docs={docs}
              onNext={next}
              onCanNextChange={setUploadHasFiles}
              onBeforeUpload={handleBeforeUpload}
            />
          )}
          {step === 1 && (
            <AnalysisStep
              caseId={caseId}
              onNext={next}
              onBack={back}
              docs={docs}
              selectedDoc={selectedDoc}
              onAnalysisStarted={() => setAnalysisStarted(true)}
              forceRefresh={forceRefresh}
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

      {/* ── Sticky Footer: Nav-Buttons ── */}
      <div style={{
        flexShrink: 0,
        background: colors.white, borderTop: `1px solid ${colors.border}`,
        padding: "12px 24px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          {showBack && (
            <Button variant="outline" size="sm" onClick={back}>
              ← Zurück
            </Button>
          )}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
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
  );
};
