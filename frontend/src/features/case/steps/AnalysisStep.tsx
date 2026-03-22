import { useState, useEffect } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon } from "../../../components";
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
  onNext: () => void;
  onBack: () => void;
}

export const AnalysisStep = ({ onNext, onBack }: AnalysisStepProps) => {
  const [analysing, setAnalysing] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [data,      setData]      = useState<ExtractedData>(MOCK_EXTRACTED);

  // Simulate async analysis – replace with real API polling
  useEffect(() => {
    const timer = setTimeout(() => setAnalysing(false), 2400);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>2. AI Analyse & Datenschutz</h3>

        {analysing ? (
          /* ── Loading state ── */
          <div style={{
            padding:        "40px 20px",
            display:        "flex",
            flexDirection:  "column",
            alignItems:     "center",
            gap:            18,
          }}>
            <div style={{
              width:        50,
              height:       50,
              border:       `3px solid ${colors.orange}`,
              borderTopColor: "transparent",
              borderRadius: "50%",
              animation:    "spin 0.9s linear infinite",
            }} />
            <div className="pulse" style={{ textAlign: "center" }}>
              <p style={{ ...textStyles.h3, fontSize: 15 }}>Dokumente werden analysiert…</p>
              <p style={textStyles.small}>
                Daten werden geschwärzt und sensible Informationen extrahiert.
              </p>
            </div>
          </div>
        ) : (
          /* ── Results ── */
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            {/* Anonymised preview */}
            <div>
              <p style={{ ...textStyles.label, marginBottom: 11 }}>Vorschau (anonymisiert)</p>
              <div style={{
                background:   colors.bg,
                border:       `1px solid ${colors.border}`,
                borderRadius: 8,
                padding:      14,
                fontSize:     13,
                lineHeight:   1.75,
                color:        colors.mid,
                fontFamily:   typography.sans,
              }}>
                Sehr geehrte/r Kundin, Ihr Rechnungsbetrag beträgt{" "}
                <span style={{
                  background:   colors.dark,
                  color:        colors.dark,
                  borderRadius: 3,
                  padding:      "1px 10px",
                  userSelect:   "none",
                }}>
                  ████████
                </span>{" "}
                und die Frist endet am 15.04.2026.
                <br /><br />
                <span style={{ fontSize: 11, color: colors.teal }}>
                  ✓ Erkannte personenbezogene Daten wurden automatisch geschwärzt.
                </span>
              </div>
            </div>

            {/* Extracted data form */}
            <div>
              <p style={{ ...textStyles.label, marginBottom: 11 }}>Erkannte Daten prüfen</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
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
          </div>
        )}
      </Card>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Button variant="outline" onClick={onBack}>Zurück</Button>
        <Button onClick={onNext} disabled={analysing} size="lg">
          Zum Roten Faden <Icon name="arrow" size={15} color="#fff" />
        </Button>
      </div>
    </div>
  );
};
