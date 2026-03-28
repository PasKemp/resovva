import { useEffect, useState } from "react";
import { colors, textStyles, typography } from "../theme/tokens";
import { Button } from "./Button";
import { caseStatusApi } from "../services/api";
import type { CaseStatusResponse } from "../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// MaskingPreview – Epic 2 (US-2.6) + Epic 8 (US-8.4)
//
// Zeigt nach erfolgreichem OCR den maskierten Text-Ausschnitt an.
// Maskierte Stellen werden farblich nach Kategorie hervorgehoben:
//   ***IBAN*** / ***@***.***  → grün  (Konto-/Kontaktdaten)
//   ***TELEFON***              → türkis (Telefonnummer)
//   ***GEBURTSDATUM***         → orange (Datums-/Geburtsdaten)
//   ***ADRESSE***              → gelb   (Anschrift/PLZ aus Nutzerprofil)
//
// Pollt GET /api/v1/cases/{caseId}/status bis Status = "completed" | "error".
// ─────────────────────────────────────────────────────────────────────────────

type MaskCategory = "privacy" | "phone" | "birthdate" | "address";

interface CategoryStyle {
  label:      string;
  background: string;
  color:      string;
  tooltip:    string;
}

const CATEGORY_STYLES: Record<MaskCategory, CategoryStyle> = {
  privacy:   {
    label:      "IBAN/E-Mail",
    background: colors.green,
    color:      colors.greenText,
    tooltip:    "IBAN/E-Mail – zu deiner Sicherheit vor der KI verborgen",
  },
  phone:     {
    label:      "Telefon",
    background: colors.tealLight,
    color:      colors.teal,
    tooltip:    "Telefonnummer – lokal entfernt",
  },
  birthdate: {
    label:      "Datum",
    background: colors.orangeLight,
    color:      colors.orange,
    tooltip:    "Datum – lokal entfernt",
  },
  address:   {
    label:      "Adresse/PLZ",
    background: colors.warningLight,
    color:      colors.warning,
    tooltip:    "Adresse/PLZ – lokal aus deinem Profil entfernt",
  },
};

function getTokenCategory(token: string): MaskCategory {
  if (token === "***TELEFON***")      return "phone";
  if (token === "***GEBURTSDATUM***") return "birthdate";
  if (token === "***ADRESSE***")      return "address";
  return "privacy";
}

function splitAndHighlight(text: string): JSX.Element[] {
  const parts = text.split(/(\*{3}[A-Z@.*]+\*{3})/g);
  return parts.map((part, i) => {
    if (/^\*{3}[A-Z@.*]+\*{3}$/.test(part)) {
      const category = getTokenCategory(part);
      const style    = CATEGORY_STYLES[category];
      return (
        <mark
          key={i}
          title={style.tooltip}
          style={{
            background:   style.background,
            color:        style.color,
            borderRadius: 4,
            padding:      "0 3px",
            fontWeight:   600,
            cursor:       "help",
            fontFamily:   typography.sans,
          }}
        >
          {part}
        </mark>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

interface MaskingPreviewProps {
  caseId: string;
  onNext: () => void;
}

export const MaskingPreview = ({ caseId, onNext }: MaskingPreviewProps) => {
  const [status,  setStatus]  = useState<CaseStatusResponse["status"] | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dots,    setDots]    = useState(".");

  // Animierte Punkte während Verarbeitung
  useEffect(() => {
    if (status === "processing" || status === null) {
      const t = setInterval(() => setDots(d => d.length >= 3 ? "." : d + "."), 500);
      return () => clearInterval(t);
    }
  }, [status]);

  // Polling bis completed oder error
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;

    async function poll() {
      try {
        const resp = await caseStatusApi.get(caseId);
        setStatus(resp.status);
        if (resp.preview) setPreview(resp.preview);

        if (resp.status === "completed" || resp.status === "error") {
          clearInterval(timer);
        }
      } catch {
        // Polling-Fehler ignorieren – nächster Versuch in 2 Sekunden
      }
    }

    poll();
    timer = setInterval(poll, 2000);
    return () => clearInterval(timer);
  }, [caseId]);

  // ── Rendering ──────────────────────────────────────────────────────────────

  if (status === null || status === "processing") {
    return (
      <div style={{
        background:   colors.bg,
        border:       `1px solid ${colors.border}`,
        borderRadius: 12,
        padding:      24,
        textAlign:    "center",
      }}>
        <div style={{
          width:          48,
          height:         48,
          borderRadius:   "50%",
          background:     colors.orangeLight,
          margin:         "0 auto 16px",
          display:        "flex",
          alignItems:     "center",
          justifyContent: "center",
          fontSize:       22,
        }}>
          🔍
        </div>
        <p style={{ ...textStyles.body, fontWeight: 600, color: colors.dark }}>
          Dokumente werden analysiert{dots}
        </p>
        <p style={{ ...textStyles.small, marginTop: 6 }}>
          Text wird extrahiert und sensible Daten werden lokal geschwärzt
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div style={{
        background:   colors.red,
        border:       `1px solid ${colors.redText}`,
        borderRadius: 12,
        padding:      24,
      }}>
        <p style={{ ...textStyles.body, color: colors.redText, fontWeight: 600 }}>
          Fehler bei der Dokumentenanalyse
        </p>
        <p style={{ ...textStyles.small, color: colors.redText, marginTop: 4 }}>
          Bitte lade die Dokumente erneut hoch oder kontaktiere den Support.
        </p>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div style={{
        background:   colors.yellow,
        border:       `1px solid ${colors.yellowBorder}`,
        borderRadius: 12,
        padding:      24,
      }}>
        <p style={{ ...textStyles.body, color: colors.yellowText }}>
          Keine Dokumente hochgeladen. Bitte lade zuerst Dokumente hoch.
        </p>
      </div>
    );
  }

  // Status === "completed"
  return (
    <div>
      {/* Erfolgs-Banner */}
      <div style={{
        background:   colors.green,
        border:       `1px solid ${colors.greenText}`,
        borderRadius: 12,
        padding:      "12px 16px",
        marginBottom: 16,
        display:      "flex",
        alignItems:   "center",
        gap:          10,
      }}>
        <span style={{ fontSize: 18 }}>✅</span>
        <p style={{ ...textStyles.body, color: colors.greenText, fontWeight: 600, margin: 0 }}>
          Dokumente erfolgreich analysiert
        </p>
      </div>

      {/* Deep-Privacy-Info (US-8.4) */}
      <div style={{
        background:   colors.tealLight,
        border:       `1px solid ${colors.teal}`,
        borderRadius: 10,
        padding:      "10px 14px",
        marginBottom: 16,
        display:      "flex",
        alignItems:   "flex-start",
        gap:          10,
      }}>
        <span style={{ fontSize: 16, flexShrink: 0 }}>🛡️</span>
        <p style={{ ...textStyles.small, color: colors.teal, margin: 0, lineHeight: 1.5 }}>
          Wir haben sensible Daten lokal erkannt und entfernt. Namen wurden zur
          Analyse beibehalten.
        </p>
      </div>

      {/* Text-Preview mit Highlighting */}
      {preview && (
        <div style={{
          background:   colors.white,
          border:       `1px solid ${colors.border}`,
          borderRadius: 12,
          padding:      20,
          marginBottom: 16,
        }}>
          <p style={{ ...textStyles.label, marginBottom: 10 }}>
            Extrahierter Text (Vorschau)
          </p>
          <div style={{
            ...textStyles.body,
            fontSize:   13,
            lineHeight: 1.8,
            whiteSpace: "pre-wrap",
            wordBreak:  "break-word",
            maxHeight:  200,
            overflowY:  "auto",
          }}>
            {splitAndHighlight(preview)}
            {preview.length >= 500 && (
              <span style={{ color: colors.muted }}> …</span>
            )}
          </div>

          {/* Farb-Legende */}
          <div style={{
            marginTop:  12,
            paddingTop: 10,
            borderTop:  `1px solid ${colors.border}`,
            display:    "flex",
            flexWrap:   "wrap",
            gap:        8,
          }}>
            {(Object.entries(CATEGORY_STYLES) as [MaskCategory, CategoryStyle][]).map(
              ([, style], i) => (
                <span
                  key={i}
                  style={{
                    background:   style.background,
                    color:        style.color,
                    borderRadius: 4,
                    padding:      "1px 6px",
                    fontSize:     11,
                    fontFamily:   typography.sans,
                    fontWeight:   600,
                  }}
                >
                  {style.label}
                </span>
              )
            )}
          </div>

          <p style={{ ...textStyles.small, marginTop: 8 }}>
            🔒 Farbig markierte Stellen wurden vor der KI-Analyse lokal entfernt.
            Das Originaldokument bleibt unverändert.
          </p>
        </div>
      )}

      {/* Weiter-Button */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button onClick={onNext} size="lg">
          Weiter zur Fall-Analyse →
        </Button>
      </div>
    </div>
  );
};
