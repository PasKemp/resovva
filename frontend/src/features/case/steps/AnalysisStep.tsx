import { useEffect, useRef, useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon, MaskingPreview } from "../../../components";
import { caseAnalyzeApi, analysisApi } from "../../../services/api";
import type { AnalysisResultResponse } from "../../../services/api";
import type { ExtractedData } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — AI Analyse & Datenschutz (Epic 3: US-3.2, US-3.3, US-3.5)
// ─────────────────────────────────────────────────────────────────────────────

type Phase = "ocr" | "analyzing" | "review";

interface AnalysisStepProps {
  caseId: string;
  onNext: () => void;
  onBack: () => void;
}

const EMPTY_DATA: ExtractedData = {
  malo_id:          null,
  meter_number:     null,
  dispute_amount:   null,
  network_operator: null,
};

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

const FIELD_CONFIG: { key: keyof ExtractedData; label: string; placeholder: string }[] = [
  { key: "malo_id",          label: "Marktlokations-ID (MaLo)",  placeholder: "DE…" },
  { key: "meter_number",     label: "Zählernummer",               placeholder: "Z123456…" },
  { key: "dispute_amount",   label: "Streitbetrag (€)",           placeholder: "274.50" },
  { key: "network_operator", label: "Netzbetreiber",              placeholder: "Stadtwerke …" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

const AnalyzingLoader = () => (
  <Card style={{ textAlign: "center", padding: "40px 24px" }}>
    <div style={{ marginBottom: 16 }}>
      <Icon name="brain" size={32} color={colors.orange} />
    </div>
    <p style={{ ...textStyles.h3, marginBottom: 8 }}>KI analysiert Ihre Dokumente…</p>
    <p style={{ ...textStyles.small, color: colors.muted }}>
      Extraktion von Zählernummer, MaLo-ID und Streitbetrag. Bitte warten.
    </p>
  </Card>
);

const MissingDataWarning = () => (
  <div style={{
    background: "#FFF7ED",
    border: `1.5px solid ${colors.orange}`,
    borderRadius: 10,
    padding: "14px 16px",
    marginBottom: 16,
    display: "flex",
    gap: 10,
    alignItems: "flex-start",
  }}>
    <Icon name="warn" size={16} color={colors.orange} />
    <div>
      <p style={{ fontFamily: typography.sans, fontSize: 13, fontWeight: 600, color: colors.orange, marginBottom: 4 }}>
        Kerndaten nicht gefunden
      </p>
      <p style={{ ...textStyles.small, color: "#92400E" }}>
        Wir konnten keine Zählernummer und keine MaLo-ID in Ihren Dokumenten finden.
        Bitte geben Sie die Daten manuell ein oder laden Sie weitere Dokumente hoch.
      </p>
    </div>
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────

export const AnalysisStep = ({ caseId, onNext, onBack }: AnalysisStepProps) => {
  const [phase,      setPhase]      = useState<Phase>("ocr");
  const [formData,   setFormData]   = useState<ExtractedData>(EMPTY_DATA);
  const [isMissing,  setIsMissing]  = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // On mount: check if analysis is already done (user navigated away and back)
  useEffect(() => {
    analysisApi.result(caseId)
      .then(resp => {
        if (resp.extracted_data) {
          applyExtractedData(resp.extracted_data);
          setPhase("review");
        }
      })
      .catch(() => {}); // 404 = still running or not started — ignore
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const applyExtractedData = (data: AnalysisResultResponse["extracted_data"]) => {
    if (!data) return;
    setFormData({
      malo_id:          data.malo_id ?? null,
      meter_number:     data.meter_number ?? null,
      dispute_amount:   data.dispute_amount ?? null,
      network_operator: data.network_operator ?? null,
    });
    setIsMissing(!!data.missing_data || (!data.malo_id && !data.meter_number));
  };

  // Start polling during "analyzing" phase
  useEffect(() => {
    if (phase !== "analyzing") return;
    pollRef.current = setInterval(() => {
      analysisApi.result(caseId)
        .then(resp => {
          if (resp.status === "error") {
            setError("Analyse fehlgeschlagen. Bitte Seite neu laden und erneut versuchen.");
            clearInterval(pollRef.current!);
            return;
          }
          if (resp.extracted_data) {
            applyExtractedData(resp.extracted_data);
            setPhase("review");
            clearInterval(pollRef.current!);
          }
        })
        .catch(() => {}); // network glitch during polling — retry next tick
    }, 2500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleOcrDone = async () => {
    setPhase("analyzing");
    setError(null);
    try {
      await caseAnalyzeApi.start(caseId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      // 409 = still processing (race condition) — keep polling
      if (!msg.includes("409")) {
        setError(`Analyse konnte nicht gestartet werden: ${msg}`);
      }
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    setError(null);
    try {
      await analysisApi.confirm(caseId, formData);
      onNext();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Bestätigung fehlgeschlagen.");
    } finally {
      setConfirming(false);
    }
  };

  const updateField = (key: keyof ExtractedData, value: string) => {
    setFormData(prev => ({
      ...prev,
      [key]: key === "dispute_amount"
        ? (value === "" ? null : parseFloat(value) || null)
        : (value || null),
    }));
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="fade-in">
      {error && (
        <div style={{ background: "#FEF2F2", border: `1px solid ${colors.redText}`, borderRadius: 8, padding: "10px 14px", marginBottom: 16 }}>
          <p style={{ ...textStyles.small, color: colors.redText }}>{error}</p>
        </div>
      )}

      {phase === "ocr" && (
        <Card>
          <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>2. AI Analyse & Datenschutz</h3>
          <MaskingPreview caseId={caseId} onNext={handleOcrDone} />
        </Card>
      )}

      {phase === "analyzing" && (
        <AnalyzingLoader />
      )}

      {phase === "review" && (
        <>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ ...textStyles.h3, marginBottom: 18 }}>2. Erkannte Daten prüfen</h3>

            {/* US-3.3: Warnung wenn Kerndaten fehlen */}
            {isMissing && <MissingDataWarning />}

            <p style={{ ...textStyles.small, color: colors.muted, marginBottom: 16 }}>
              Bitte prüfen und ggf. korrigieren Sie die erkannten Informationen.
              Fehlende Felder können Sie manuell ausfüllen.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 400 }}>
              {FIELD_CONFIG.map(({ key, label, placeholder }) => (
                <div key={key}>
                  <p style={{ ...textStyles.small, marginBottom: 4 }}>{label}</p>
                  <input
                    value={
                      key === "dispute_amount"
                        ? (formData[key] != null ? String(formData[key]) : "")
                        : (formData[key] as string | null) ?? ""
                    }
                    onChange={e => updateField(key, e.target.value)}
                    placeholder={placeholder}
                    style={{
                      ...INPUT_STYLE,
                      borderColor: formData[key] != null ? colors.teal : colors.border,
                    }}
                  />
                  {formData[key] != null && (
                    <p style={{ fontSize: 10, color: colors.teal, marginTop: 2, fontFamily: typography.sans }}>
                      ✓ KI-erkannt
                    </p>
                  )}
                </div>
              ))}
            </div>

            {isMissing && (
              <div style={{ marginTop: 16 }}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onBack}
                  style={{ gap: 6 }}
                >
                  <Icon name="upload" size={13} color={colors.orange} />
                  Weiteres Dokument hochladen
                </Button>
              </div>
            )}
          </Card>

          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <Button variant="outline" onClick={onBack}>Zurück</Button>
            <Button
              onClick={handleConfirm}
              disabled={confirming}
              size="lg"
            >
              {confirming ? "Wird gespeichert…" : (
                <>Bestätigen & weiter <Icon name="arrow" size={15} color="#fff" /></>
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
};
