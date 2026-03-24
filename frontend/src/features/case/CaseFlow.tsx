import { useEffect, useRef, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Icon } from "../../components";
import { UploadStep } from "./steps/UploadStep";
import { AnalysisStep } from "./steps/AnalysisStep";
import { TimelineStep } from "./steps/TimelineStep";
import { CheckoutStep } from "./steps/CheckoutStep";
import { casesApi, caseStatusApi } from "../../services/api";
import type { Page, WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// CaseFlow — 4-Schritt-Wizard (US-7.7: Stepper-Navigation & Dokument-Sidebar)
// ─────────────────────────────────────────────────────────────────────────────

type StepIndex = 0 | 1 | 2 | 3;

interface StepMeta {
  label: string;
  sublabel: string;
  icon: string;
}

// Schritt-Beschreibungstexte (US-7.7: in separater Konstante pflegbar)
const STEPS: StepMeta[] = [
  { label: "Upload", sublabel: "Dokumente & Scan", icon: "upload" },
  { label: "Analyse", sublabel: "KI & Datenschutz", icon: "brain" },
  { label: "Roter Faden", sublabel: "Chronologie", icon: "list" },
  { label: "Abschluss", sublabel: "Überblick & Zahlung", icon: "folder" },
];

// ── Stepper ───────────────────────────────────────────────────────────────────

interface StepperProps {
  current: StepIndex;
  onStep: (i: StepIndex) => void;
}

const StepDot = ({ index, current }: { index: number; current: number }) => {
  const done = index < current;
  const active = index === current;
  return (
    <div style={{
      width: 34,
      height: 34,
      borderRadius: "50%",
      background: done ? colors.teal : active ? colors.orange : colors.bg,
      border: `2px solid ${done ? colors.teal : active ? colors.orange : colors.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      transition: "all .3s ease",
    }}>
      {done
        ? <Icon name="check" size={14} color="#fff" />
        : <span style={{
          fontSize: 12, fontWeight: 700, fontFamily: typography.sans,
          color: active ? "#fff" : colors.muted,
        }}>
          {index + 1}
        </span>
      }
    </div>
  );
};

const Stepper = ({ current, onStep }: StepperProps) => (
  <div style={{
    background: colors.white,
    borderRadius: 14,
    border: `1px solid ${colors.border}`,
    padding: "16px 24px",
    marginBottom: 24,
    display: "flex",
    alignItems: "center",
  }}>
    {STEPS.map((step, i) => (
      <div
        key={i}
        style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : 0, minWidth: 0 }}
      >
        <div
          onClick={() => onStep(i as StepIndex)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            cursor: i <= current ? "pointer" : "default",
            flexShrink: 0,
            opacity: i > current ? 0.5 : 1,
            transition: "opacity .2s",
          }}
        >
          <StepDot index={i} current={current} />
          <div style={{ overflow: "hidden" }}>
            <p style={{
              fontSize: 11,
              fontWeight: 600,
              fontFamily: typography.sans,
              color: i < current ? colors.teal : i === current ? colors.orange : colors.muted,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              lineHeight: 1.2,
              whiteSpace: "nowrap",
            }}>
              {step.label}
            </p>
            <p style={{
              fontSize: 12,
              fontFamily: typography.sans,
              color: i === current ? colors.dark : colors.muted,
              fontWeight: i === current ? 600 : 400,
              lineHeight: 1.3,
              whiteSpace: "nowrap",
            }}>
              {step.sublabel}
            </p>
          </div>
        </div>

        {i < STEPS.length - 1 && (
          <div style={{
            flex: 1,
            height: 2,
            background: i < current ? colors.teal : colors.border,
            margin: "0 12px",
            borderRadius: 2,
            transition: "background .4s ease",
            minWidth: 16,
          }} />
        )}
      </div>
    ))}
  </div>
);

// ── Dokument-Seitenleiste (US-7.7) ───────────────────────────────────────────

interface DocEntry {
  document_id: string;
  filename: string;
  ocr_status: string;
  created_at: string;
}

const DocumentSidebar = ({ caseId }: { caseId: string }) => {
  const [docs, setDocs] = useState<DocEntry[]>([]);

  useEffect(() => {
    const load = () => {
      caseStatusApi.listDocuments(caseId)
        .then(r => setDocs(r.documents))
        .catch(() => { });
    };
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [caseId]);

  return (
    <div style={{
      width: 260,
      background: colors.white,
      border: `1px solid ${colors.border}`,
      borderRadius: 14,
      padding: "18px 16px",
      flexShrink: 0,
      alignSelf: "flex-start",
      position: "sticky",
      top: 24,
    }}>
      <p style={{ ...textStyles.label, marginBottom: 14 }}>
        Dokumente ({docs.length})
      </p>

      {docs.length === 0 && (
        <p style={{ ...textStyles.small, color: colors.muted, textAlign: "center", padding: "16px 0" }}>
          Noch keine Dokumente
        </p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {docs.map(d => (
          <div key={d.document_id} style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 10px",
            background: colors.bg,
            borderRadius: 8,
          }}>
            <div style={{
              width: 28, height: 28,
              background: colors.orangeLight, borderRadius: 6,
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
            }}>
              <Icon name="file" size={13} color={colors.orange} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontFamily: typography.sans, fontSize: 12, fontWeight: 600,
                color: colors.dark, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {d.filename}
              </p>
              <p style={{
                ...textStyles.small, fontSize: 11,
                color: d.ocr_status === "completed" ? colors.greenText
                  : d.ocr_status === "error" ? colors.redText
                    : colors.muted,
              }}>
                {d.ocr_status === "completed" ? "✓ Analysiert"
                  : d.ocr_status === "error" ? "✗ Fehler"
                    : d.ocr_status === "processing" ? "⏳ Verarbeitung…"
                      : "⏳ Wartend"}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── CaseFlow ─────────────────────────────────────────────────────────────────

interface CaseFlowProps extends WithSetPage {
  caseId?: string;
}

export const CaseFlow = ({ setPage, caseId: initialCaseId }: CaseFlowProps) => {
  const [step, setStep] = useState<StepIndex>(0);
  const [caseId, setCaseId] = useState<string | null>(initialCaseId ?? null);
  const [caseError, setCaseError] = useState<string | null>(null);
  // Ref-Guard gegen React-StrictMode-Doppel-Invoke: useEffect feuert in DEV
  // zweimal (mount → unmount → remount). Ohne Guard würden 2 Fälle angelegt.
  const hasCreatedRef = useRef(false);

  useEffect(() => {
    if (caseId || hasCreatedRef.current) return;
    hasCreatedRef.current = true;
    casesApi.create()
      .then(r => setCaseId(r.case_id))
      .catch(() => {
        hasCreatedRef.current = false; // Reset bei Fehler damit Retry möglich
        setCaseError("Fall konnte nicht erstellt werden. Bitte Seite neu laden.");
      });
  }, []);

  // US-7.7: Zurücknavigation – nur zu bereits besuchten Schritten
  const goTo = (i: StepIndex) => { if (i <= step) setStep(i); };
  const next = () => setStep(s => Math.min(s + 1, 3) as StepIndex);
  const back = () => setStep(s => Math.max(s - 1, 0) as StepIndex);

  if (caseError) {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "48px 24px", textAlign: "center" }}>
        <p style={{ ...textStyles.body, color: colors.redText }}>{caseError}</p>
      </div>
    );
  }

  if (!caseId) {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "48px 24px", textAlign: "center" }}>
        <p style={{ ...textStyles.body, color: colors.muted }}>Fall wird vorbereitet…</p>
      </div>
    );
  }

  return (
    // US-7.7: maxWidth auf 1100px erweitert für 2-Spalten-Layout
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px 48px" }}>
      {/* Zurück zur Übersicht – außerhalb des Steppers, kein Overlap */}
      <div style={{ marginBottom: 12 }}>
        <button
          onClick={() => setPage("dashboard")}
          style={{
            background: "none", border: "none", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6,
            fontFamily: "inherit", fontSize: 13, color: "#6B7280", padding: "4px 0",
          }}
        >
          ← Übersicht
        </button>
      </div>
      <Stepper current={step} onStep={goTo} />

      {/* US-7.7: Content + Dokument-Seitenleiste */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* Haupt-Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {step === 0 && <UploadStep caseId={caseId} onNext={next} />}
          {step === 1 && <AnalysisStep caseId={caseId} onNext={next} onBack={back} />}
          {step === 2 && <TimelineStep caseId={caseId} onNext={next} onBack={back} />}
          {step === 3 && <CheckoutStep caseId={caseId} onBack={back} setPage={setPage} />}
        </div>

        {/* Persistente Dokument-Seitenleiste (US-7.7) */}
        <DocumentSidebar caseId={caseId} />
      </div>
    </div>
  );
};
