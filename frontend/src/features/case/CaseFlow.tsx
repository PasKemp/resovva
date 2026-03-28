import { useEffect, useRef, useState, useCallback } from "react";
import { colors, textStyles } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import { InitialSetupStep } from "./steps/InitialSetupStep";
import { UploadStep } from "./steps/UploadStep";
import { AnalysisStep } from "./steps/AnalysisStep";
import { TimelineStep } from "./steps/TimelineStep";
import { CheckoutStep } from "./steps/CheckoutStep";
import { casesApi, caseStatusApi } from "../../services/api";
import type { DocumentListItem } from "../../services/api";
import type { WithSetPage } from "../../types";
import { Stepper } from "./components/Stepper";
import { DocNav } from "./components/DocNav";
import { ResetWarningDialog } from "./components/ResetWarningDialog";

// ── CaseFlow ─────────────────────────────────────────────────────────────────

type StepIndex = 0 | 1 | 2 | 3 | 4;

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

  const [step0CanProceed,  setStep0CanProceed]  = useState(false);
  const [recommendedDocs,  setRecommendedDocs]  = useState<string[]>([]);

  const step0ActionRef  = useRef<() => void>(() => {});
  const step1ActionRef  = useRef<() => void>(() => {});
  const hasCreatedRef   = useRef(false);
  const resolveResetRef = useRef<((v: boolean) => void) | null>(null);

  const handleStep0ActionChange = useCallback((cfg: { canProceed: boolean; handler: () => void }) => {
    step0ActionRef.current = cfg.handler;
    setStep0CanProceed(prev => prev === cfg.canProceed ? prev : cfg.canProceed);
  }, []);

  const handleStep1ActionChange = useCallback((cfg: { label: string; disabled: boolean; handler: () => void }) => {
    step1ActionRef.current = cfg.handler;
    setStep1Btn(prev => {
      if (prev.label === cfg.label && prev.disabled === cfg.disabled) return prev;
      return { label: cfg.label, disabled: cfg.disabled };
    });
  }, []);

  const handleAnalysisStarted = useCallback(() => {
    setAnalysisStarted(true);
  }, []);

  // "Weiter" aktiv: Step 1 (Upload) nur wenn Dateien vorhanden, Step 3 (Timeline) immer
  const canNext  = step === 1 ? uploadHasFiles : step === 3;
  const showNext = step === 1 || step === 3;
  const showBack = step > 0;

  // Step-Änderungen melden
  useEffect(() => { onStepChange?.(step); }, [step, onStepChange]);

  // Sidebar automatisch einklappen wenn Schritt > 1 (Upload-Step)
  useEffect(() => { setSidebarOpen(step === 1); }, [step]);

  // Fall anlegen (StrictMode-Guard: leeres Array ist bewusst — einmaliger Mount-Effekt)
  useEffect(() => {
    if (caseId || hasCreatedRef.current) return;
    hasCreatedRef.current = true;
    casesApi.create()
      .then(r => { setCaseId(r.case_id); onCaseCreated?.(r.case_id); })
      .catch(() => { hasCreatedRef.current = false; setCaseError("Fall konnte nicht erstellt werden. Bitte Seite neu laden."); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps 

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
      // Nur API aufrufen, wenn wir im Upload-Step (1) sind ODER Dokumente gerade noch verarbeitet werden
      if (stepRef.current === 1 || hasPending) {
        load();
      }
    }, 2000);
    
    return () => clearInterval(t);
  }, [caseId]);

  // Erstes Dokument automatisch selektieren
  useEffect(() => {
    if (docs.length > 0 && !selectedDocId) setSelectedDocId(docs[0].document_id);
  }, [docs, selectedDocId]);

  const goTo = (i: number) => { if (i <= step) setStep(i as StepIndex); };
  const next = useCallback(() => setStep(s => Math.min(s + 1, 4) as StepIndex), []);
  const back = useCallback(() => setStep(s => Math.max(s - 1, 0) as StepIndex), []);

  const handleContextSaved = useCallback((docs: string[]) => {
    setRecommendedDocs(docs);
    next();
  }, [next]);

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
    <div style={styles.errorContainer}>
      <p style={{ ...textStyles.body, color: colors.redText }}>{caseError}</p>
    </div>
  );

  if (!caseId) return (
    <div style={styles.loadingContainer}>
      <p style={{ ...textStyles.body, color: colors.muted }}>Fall wird vorbereitet…</p>
    </div>
  );

  return (
    <div style={styles.root}>

      {showResetDialog && (
        <ResetWarningDialog onConfirm={confirmReset} onCancel={cancelReset} />
      )}

      {/* ── Oberer Bereich: Zurück zur Übersicht + Stepper ── */}
      <div style={styles.topSection}>

        {/* Zurück zur Übersicht */}
        <button onClick={() => setPage("dashboard")} style={styles.backToDashboard}>
          ← Übersicht
        </button>

        {/* Stepper */}
        <Stepper current={step} onStep={goTo} />
      </div>

      {/* ── Haupt-Bereich: DocNav links | Step-Inhalt rechts ── */}
      <div style={styles.mainArea}>

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
          ...styles.contentWrapper,
          overflowY: step === 2 ? "hidden" : "auto",
        }}>
          {step === 0 && (
            <InitialSetupStep
              caseId={caseId}
              onActionChange={handleStep0ActionChange}
              onContextSaved={handleContextSaved}
            />
          )}
          {step === 1 && (
            <UploadStep
              caseId={caseId}
              docs={docs}
              onNext={next}
              onCanNextChange={setUploadHasFiles}
              onBeforeUpload={handleBeforeUpload}
              recommendedDocs={recommendedDocs}
            />
          )}
          {step === 2 && (
            <AnalysisStep
              caseId={caseId}
              onNext={next}
              onBack={back}
              docs={docs}
              selectedDoc={selectedDoc}
              onAnalysisStarted={handleAnalysisStarted}
              forceRefresh={forceRefresh}
              onActionChange={handleStep1ActionChange}
            />
          )}
          {step === 3 && <TimelineStep caseId={caseId} onNext={next} onBack={back} onGoToUpload={() => setStep(1)} />}
          {step === 4 && <CheckoutStep caseId={caseId} onBack={back} setPage={setPage} />}
        </div>
      </div>

      {/* ── Sticky Footer: Nav-Buttons ── */}
      <div style={styles.footer}>
        <div>
          {showBack && (
            <Button variant="outline" size="sm" onClick={back}>
              ← Zurück
            </Button>
          )}
        </div>
        <div style={styles.footerButtonsRight}>
          {step === 0 && (
            <Button size="sm" onClick={() => step0ActionRef.current()} disabled={!step0CanProceed}>
              Weiter <Icon name="arrow" size={13} color="#fff" />
            </Button>
          )}
          {showNext && (
            <Button size="sm" onClick={next} disabled={!canNext}>
              Weiter <Icon name="arrow" size={13} color="#fff" />
            </Button>
          )}
          {step === 2 && (
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

const styles = {
  root: {
    display: "flex" as const,
    flexDirection: "column" as const,
    height: "100%",
    overflow: "hidden",
  },
  errorContainer: {
    padding: "48px 24px",
    textAlign: "center" as const,
  },
  loadingContainer: {
    padding: "48px 24px",
    textAlign: "center" as const,
  },
  topSection: {
    padding: "10px 20px 10px",
    flexShrink: 0,
    background: colors.white,
    borderBottom: `1px solid ${colors.border}`,
  },
  backToDashboard: {
    background: "none",
    border: "none",
    cursor: "pointer",
    display: "inline-flex" as const,
    alignItems: "center" as const,
    gap: 6,
    fontFamily: "inherit",
    fontSize: 12,
    color: colors.muted,
    padding: "0 0 8px 0",
  },
  mainArea: {
    flex: 1,
    display: "flex" as const,
    overflow: "hidden",
  },
  contentWrapper: {
    flex: 1,
    minWidth: 0,
    display: "flex" as const,
    flexDirection: "column" as const,
    padding: "24px 32px",
    background: colors.bg,
  },
  footer: {
    flexShrink: 0,
    background: colors.white,
    borderTop: `1px solid ${colors.border}`,
    padding: "12px 24px",
    display: "flex" as const,
    justifyContent: "space-between" as const,
    alignItems: "center" as const,
  },
  footerButtonsRight: {
    display: "flex" as const,
    gap: 10,
  },
};
