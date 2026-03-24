import { useEffect, useState } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Icon } from "../../components";
import { UploadStep }   from "./steps/UploadStep";
import { AnalysisStep } from "./steps/AnalysisStep";
import { TimelineStep } from "./steps/TimelineStep";
import { CheckoutStep } from "./steps/CheckoutStep";
import { casesApi }     from "../../services/api";
import type { Page, WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// CaseFlow — 4-step wizard container
// ─────────────────────────────────────────────────────────────────────────────

type StepIndex = 0 | 1 | 2 | 3;

interface StepMeta {
  label:    string;
  sublabel: string;
}

const STEPS: StepMeta[] = [
  { label: "Upload",       sublabel: "Dokumente & Scan" },
  { label: "Analyse",      sublabel: "AI & Datenschutz" },
  { label: "Roter Faden",  sublabel: "Chronologie" },
  { label: "Abschluss",    sublabel: "Checkout" },
];

// ── ProgressBar ─────────────────────────────────────────────────────────────

interface ProgressBarProps {
  current:  StepIndex;
  onStep:   (i: StepIndex) => void;
  setPage:  (p: Page) => void;
}

const StepDot = ({
  index, current,
}: { index: number; current: number }) => {
  const done   = index < current;
  const active = index === current;

  return (
    <div style={{
      width:        30,
      height:       30,
      borderRadius: "50%",
      background:   done ? colors.teal : active ? colors.orange : colors.bg,
      border:       `2px solid ${done ? colors.teal : active ? colors.orange : colors.border}`,
      display:      "flex",
      alignItems:   "center",
      justifyContent: "center",
      flexShrink:   0,
      transition:   "all .3s ease",
    }}>
      {done
        ? <Icon name="check" size={13} color="#fff" />
        : <span style={{
            fontSize:   11,
            fontWeight: 700,
            fontFamily: typography.sans,
            color:      active ? "#fff" : colors.muted,
          }}>
            {index + 1}
          </span>
      }
    </div>
  );
};

const ProgressBar = ({ current, onStep, setPage }: ProgressBarProps) => (
  <div style={{
    background:   colors.white,
    borderRadius: 12,
    border:       `1px solid ${colors.border}`,
    padding:      "14px 20px",
    marginBottom: 24,
    display:      "flex",
    alignItems:   "center",
    gap:          0,
  }}>
    {STEPS.map((step, i) => (
      <div
        key={i}
        style={{
          display:  "flex",
          alignItems: "center",
          flex:     i < STEPS.length - 1 ? 1 : 0,
          minWidth: 0,
        }}
      >
        {/* Step item */}
        <div
          onClick={() => onStep(i as StepIndex)}
          style={{
            display:    "flex",
            alignItems: "center",
            gap:        10,
            cursor:     i <= current ? "pointer" : "default",
            flexShrink: 0,
          }}
        >
          <StepDot index={i} current={current} />
          <div>
            <p style={{
              fontSize:   10,
              fontWeight: 600,
              fontFamily: typography.sans,
              color:      i < current ? colors.teal : i === current ? colors.orange : colors.muted,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              lineHeight: 1.2,
            }}>
              {step.label}
            </p>
            <p style={{
              fontSize:   11,
              fontFamily: typography.sans,
              color:      i === current ? colors.dark : colors.muted,
              fontWeight: i === current ? 600 : 400,
              lineHeight: 1.3,
            }}>
              {step.sublabel}
            </p>
          </div>
        </div>

        {/* Connector */}
        {i < STEPS.length - 1 && (
          <div style={{
            flex:         1,
            height:       2,
            background:   i < current ? colors.teal : colors.border,
            margin:       "0 12px",
            borderRadius: 2,
            transition:   "background .4s ease",
          }} />
        )}
      </div>
    ))}

    {/* Overview button */}
    <button
      onClick={() => setPage("dashboard")}
      style={{
        background:   colors.bg,
        border:       `1px solid ${colors.border}`,
        borderRadius: 20,
        padding:      "5px 15px",
        fontSize:     12,
        fontWeight:   600,
        fontFamily:   typography.sans,
        color:        colors.mid,
        cursor:       "pointer",
        flexShrink:   0,
        marginLeft:   18,
        transition:   "border-color .18s",
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = colors.mid)}
      onMouseLeave={e => (e.currentTarget.style.borderColor = colors.border)}
    >
      Fall Überblick
    </button>
  </div>
);

// ── CaseFlow ───────────────────────────────────────────────────────────────

interface CaseFlowProps extends WithSetPage {
  caseId?: string;
}

export const CaseFlow = ({ setPage, caseId: initialCaseId }: CaseFlowProps) => {
  const [step,   setStep]   = useState<StepIndex>(0);
  const [caseId, setCaseId] = useState<string | null>(initialCaseId ?? null);
  const [caseError, setCaseError] = useState<string | null>(null);

  // Falls keine caseId übergeben, automatisch neuen Fall anlegen
  useEffect(() => {
    if (caseId) return;
    casesApi.create()
      .then(r => setCaseId(r.case_id))
      .catch(() => setCaseError("Fall konnte nicht erstellt werden. Bitte Seite neu laden."));
  }, []);

  const goTo = (i: StepIndex) => {
    if (i <= step) setStep(i);
  };

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
    <div style={{
      maxWidth: 720,
      margin:   "0 auto",
      padding:  "28px 24px 48px",
    }}>
      <ProgressBar current={step} onStep={goTo} setPage={setPage} />

      {step === 0 && <UploadStep   caseId={caseId} onNext={next} />}
      {step === 1 && <AnalysisStep caseId={caseId} onNext={next} onBack={back} />}
      {step === 2 && <TimelineStep caseId={caseId} onNext={next} onBack={back} />}
      {step === 3 && <CheckoutStep caseId={caseId} onBack={back} setPage={setPage} />}
    </div>
  );
};
