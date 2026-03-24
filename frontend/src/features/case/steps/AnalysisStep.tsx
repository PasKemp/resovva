import { useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon, MaskingPreview } from "../../../components";
import type { ExtractedData } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — AI Analyse & Datenschutz
// ─────────────────────────────────────────────────────────────────────────────

const MOCK_EXTRACTED: ExtractedData = {
  malo:     "DE123456789012345678990",
  zaehlerNr:"Z123456789",
  betrag:   "€ 274.50",
};

const FIELD_LABELS: { key: keyof ExtractedData; label: string }[] = [
  { key: "malo",      label: "MaLo" },
  { key: "zaehlerNr", label: "Zählernummer" },
  { key: "betrag",    label: "Betrag" },
];

const INPUT_STYLE: React.CSSProperties = {
  width:        "100%",
  padding:      "10px 14px",
  border:       `1.5px solid ${colors.border}`,
  borderRadius: 8,
  fontSize:     13,
  fontFamily:   typography.sans,
  color:        colors.dark,
  outline:      "none",
  background:   colors.bg,
};

interface AnalysisStepProps {
  caseId: string;
  onNext: () => void;
  onBack: () => void;
}

export const AnalysisStep = ({ caseId, onNext, onBack }: AnalysisStepProps) => {
  const [ocrDone,   setOcrDone]   = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [data,      setData]      = useState<ExtractedData>(MOCK_EXTRACTED);

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>2. AI Analyse & Datenschutz</h3>

        {/* MaskingPreview pollt den OCR-Status und zeigt den maskierten Text */}
        {!ocrDone ? (
          <MaskingPreview caseId={caseId} onNext={() => setOcrDone(true)} />
        ) : (
          /* ── Extrahierte Daten zur Prüfung ── */
          <div>
            <p style={{ ...textStyles.label, marginBottom: 14 }}>Erkannte Daten prüfen & bestätigen</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 11, maxWidth: 360 }}>
              {FIELD_LABELS.map(({ key, label }) => (
                <div key={key}>
                  <p style={{ ...textStyles.small, marginBottom: 4 }}>{label}</p>
                  <input
                    value={data[key]}
                    onChange={e => setData(prev => ({ ...prev, [key]: e.target.value }))}
                    style={INPUT_STYLE}
                  />
                </div>
              ))}
              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <Button
                  onClick={() => setConfirmed(true)}
                  size="sm"
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  {confirmed
                    ? <><Icon name="check" size={13} color="#fff" /> Bestätigt</>
                    : "Bestätigen"}
                </Button>
                <Button variant="outline" size="sm" style={{ flex: 1, justifyContent: "center" }}>
                  Korrigieren
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {ocrDone && (
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Button variant="outline" onClick={onBack}>Zurück</Button>
          <Button onClick={onNext} disabled={!confirmed} size="lg">
            Zum Roten Faden <Icon name="arrow" size={15} color="#fff" />
          </Button>
        </div>
      )}
    </div>
  );
};
