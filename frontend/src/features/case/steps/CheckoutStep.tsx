import { useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon } from "../../../components";
import type { Page } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 4 — Paywall & Checkout
// ─────────────────────────────────────────────────────────────────────────────

const DOSSIER_FEATURES = [
  "Vollständige Beweischronologie",
  "Anonymisierte Dokumentenanlage",
  "Juristische Zusammenfassung",
  "PDF bereit für Schlichtungsstelle",
] as const;

interface CheckoutStepProps {
  caseId:  string;
  onBack:  () => void;
  setPage: (p: Page) => void;
}

export const CheckoutStep = ({ caseId: _caseId, onBack, setPage }: CheckoutStepProps) => {
  const [agreed, setAgreed] = useState(false);

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 20 }}>4. Paywall & Checkout</h3>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 230px", gap: 28, alignItems: "start" }}>
          {/* ── Left: description ── */}
          <div>
            <p style={{ ...textStyles.body, marginBottom: 18 }}>
              Deine juristische Chronologie steht. Generiere jetzt dein professionelles Dossier.
            </p>

            {/* Info notice */}
            <div style={{
              background:   colors.tealLight,
              border:       `1px solid ${colors.teal}30`,
              borderRadius: 9,
              padding:      "13px 15px",
              marginBottom: 20,
            }}>
              <p style={{ fontSize: 12, color: colors.teal, fontFamily: typography.sans, lineHeight: 1.6 }}>
                Das Dossier enthält die rechtlich relevanten Dokumente, die Chronologie
                und eine juristische Zusammenfassung.
              </p>
            </div>

            {/* Feature list */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {DOSSIER_FEATURES.map(f => (
                <div key={f} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Icon name="checkCircle" size={16} color={colors.teal} />
                  <span style={{ fontSize: 13, color: colors.mid, fontFamily: typography.sans }}>
                    {f}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right: price box ── */}
          <div style={{
            background:   colors.bg,
            border:       `1px solid ${colors.border}`,
            borderRadius: 13,
            padding:      "22px 18px",
          }}>
            <p style={{ ...textStyles.label, marginBottom: 8 }}>Preis</p>
            <div style={{
              fontFamily: "'DM Serif Display', Georgia, serif",
              fontSize:   38,
              color:      colors.dark,
              marginBottom: 4,
            }}>
              20,00 €
            </div>
            <p style={{ fontSize: 11, color: colors.muted, fontFamily: typography.sans, marginBottom: 20 }}>
              Einmalzahlung · Kein Abo
            </p>

            <label style={{
              display:     "flex",
              alignItems:  "flex-start",
              gap:         9,
              cursor:      "pointer",
              marginBottom: 18,
            }}>
              <input
                type="checkbox"
                checked={agreed}
                onChange={e => setAgreed(e.target.checked)}
                style={{ marginTop: 3, accentColor: colors.orange, width: 14, height: 14, flexShrink: 0 }}
              />
              <span style={{ fontSize: 11, color: colors.muted, fontFamily: typography.sans, lineHeight: 1.5 }}>
                Ich habe das Widerrufsrecht gelesen und akzeptiere die Bedingungen.
              </span>
            </label>

            <Button
              onClick={() => setPage("dossier")}
              disabled={!agreed}
              size="md"
              style={{ width: "100%", justifyContent: "center" }}
            >
              Kostenpflichtig bestellen
            </Button>
          </div>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-start" }}>
        <Button variant="outline" onClick={onBack}>Zurück</Button>
      </div>
    </div>
  );
};
