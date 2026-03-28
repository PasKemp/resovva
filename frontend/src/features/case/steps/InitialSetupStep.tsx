import React, { useEffect, useState } from "react";
import { Card } from "../../../components";
import { casesApi } from "../../../services/api";
import { colors, textStyles, typography } from "../../../theme/tokens";

// ── Konstanten ────────────────────────────────────────────────────────────────

const CATEGORY_OPTIONS = [
  "Abrechnungsfehler",
  "Kündigungsprobleme",
  "Anbieterwechsel-Chaos",
  "PV-Anlage/Einspeisung",
  "Sonstiges",
] as const;

const GOAL_OPTIONS = [
  "Korrekte Abrechnung erhalten",
  "Kündigung bestätigen lassen",
  "Geld zurückfordern",
] as const;

const MAX_DESCRIPTION_LENGTH = 1000;

// ── Typen ─────────────────────────────────────────────────────────────────────

interface ActionConfig {
  canProceed: boolean;
  handler:    () => void;
}

interface InitialSetupStepProps {
  caseId:          string;
  onActionChange:  (cfg: ActionConfig) => void;
  onContextSaved:  (recommendedDocs: string[]) => void;
}

// ── Komponente ────────────────────────────────────────────────────────────────

export const InitialSetupStep: React.FC<InitialSetupStepProps> = ({
  caseId,
  onActionChange,
  onContextSaved,
}) => {
  const [opponentName, setOpponentName] = useState("");
  const [category,     setCategory]     = useState("");
  const [goal,         setGoal]         = useState("");
  const [description,  setDescription]  = useState("");
  const [submitting,   setSubmitting]   = useState(false);
  const [apiError,     setApiError]     = useState<string | null>(null);

  const allFilled =
    opponentName.trim().length > 0 &&
    category.length > 0 &&
    goal.length > 0 &&
    description.trim().length > 0;

  useEffect(() => {
    const handler = async () => {
      if (!allFilled || submitting) return;
      setSubmitting(true);
      setApiError(null);
      try {
        const resp = await casesApi.setContext(caseId, {
          opponent_name: opponentName.trim(),
          category,
          goal,
          description: description.trim(),
        });
        onContextSaved(resp.recommended_docs);
      } catch {
        setApiError("Fehler beim Speichern. Bitte erneut versuchen.");
        setSubmitting(false);
      }
    };

    onActionChange({ canProceed: allFilled && !submitting, handler });
  }, [allFilled, submitting, opponentName, category, goal, description, caseId, onActionChange, onContextSaved]);

  return (
    <Card>
      <h3 style={{ ...textStyles.h3, marginBottom: 6 }}>Fall-Steckbrief</h3>
      <p style={{ ...textStyles.body, color: colors.mid, marginBottom: 24 }}>
        Beschreibe deinen Fall kurz, bevor du Dokumente hochlädst.
        Resovva nutzt diese Angaben, um dir gezielt zu helfen.
      </p>

      {/* Feld 1: Streitpartei */}
      <label style={styles.label}>Name der Streitpartei?</label>
      <input
        type="text"
        value={opponentName}
        onChange={e => setOpponentName(e.target.value)}
        placeholder="z.B. Stadtwerke München, E.ON…"
        style={styles.input}
      />

      {/* Feld 2: Kategorie */}
      <label style={styles.label}>Worum geht es?</label>
      <select
        value={category}
        onChange={e => setCategory(e.target.value)}
        style={styles.input}
      >
        <option value="">Bitte wählen…</option>
        {CATEGORY_OPTIONS.map(opt => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>

      {/* Feld 3: Ziel */}
      <label style={styles.label}>Was ist dein Ziel?</label>
      <select
        value={goal}
        onChange={e => setGoal(e.target.value)}
        style={styles.input}
      >
        <option value="">Bitte wählen…</option>
        {GOAL_OPTIONS.map(opt => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>

      {/* Feld 4: Beschreibung */}
      <label style={styles.label}>
        Beschreibe den Fall kurz in deinen Worten
        <span style={styles.charCount}>
          {description.length}/{MAX_DESCRIPTION_LENGTH}
        </span>
      </label>
      <textarea
        value={description}
        onChange={e => setDescription(e.target.value.slice(0, MAX_DESCRIPTION_LENGTH))}
        rows={5}
        placeholder="Was ist passiert? Seit wann? Welcher Betrag ist strittig?"
        style={{ ...styles.input, resize: "vertical", minHeight: 120 }}
      />

      {apiError && (
        <p style={{ fontFamily: typography.sans, fontSize: 12, color: colors.redText, marginTop: 10 }}>
          {apiError}
        </p>
      )}

      {submitting && (
        <p style={{ ...textStyles.small, color: colors.muted, marginTop: 10 }}>
          Wird gespeichert…
        </p>
      )}
    </Card>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = {
  label: {
    ...textStyles.label,
    display:       "block" as const,
    marginBottom:  6,
    marginTop:     18,
    textTransform: "uppercase" as const,
  },
  charCount: {
    fontFamily:    typography.sans,
    fontSize:      11,
    color:         colors.muted,
    fontWeight:    400,
    textTransform: "none" as const,
    marginLeft:    8,
  },
  input: {
    width:       "100%",
    padding:     "10px 12px",
    fontFamily:  typography.sans,
    fontSize:    13,
    border:      `1.5px solid ${colors.border}`,
    borderRadius: 8,
    outline:     "none",
    background:  colors.white,
    color:       colors.dark,
    boxSizing:   "border-box" as const,
  } as React.CSSProperties,
};
