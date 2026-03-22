import { useState, useEffect } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Card, Icon } from "../../components";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// DossierScreen — animated generation progress screen
// ─────────────────────────────────────────────────────────────────────────────

const GENERATION_STEPS = [
  "Dokumente prüfen",
  "Chronologie erstellen",
  "Anlagen nummerieren",
  "PDF generieren",
  "Qualitätskontrolle",
] as const;

// ── Sub-components ─────────────────────────────────────────────────────────

interface StepItemProps {
  label:   string;
  index:   number;
  current: number;
  done:    boolean;
}

const StepItem = ({ label, index, current, done }: StepItemProps) => {
  const isActive = index === current && !done;
  const isDone   = index < current || done;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{
        width:        24,
        height:       24,
        borderRadius: "50%",
        background:   isDone ? colors.teal : isActive ? colors.orange : colors.bg,
        border:       `2px solid ${isDone ? colors.teal : isActive ? colors.orange : colors.border}`,
        display:      "flex",
        alignItems:   "center",
        justifyContent: "center",
        flexShrink:   0,
        transition:   "all .4s ease",
      }}>
        {isDone && <Icon name="check" size={12} color="#fff" />}
        {isActive && (
          <span className="spin" style={{ fontSize: 11, color: "#fff", display: "inline-block" }}>⟳</span>
        )}
      </div>
      <span style={{
        fontSize:   13,
        fontFamily: typography.sans,
        color:      isDone ? colors.teal : isActive ? colors.dark : colors.muted,
        fontWeight: isActive ? 600 : 400,
        transition: "color .3s ease",
      }}>
        {label}
      </span>
    </div>
  );
};

// ── DossierScreen ───────────────────────────────────────────────────────────

export const DossierScreen = ({ setPage }: WithSetPage) => {
  const [progress, setProgress] = useState(0);

  // Simulate generation progress — replace with dossierApi.status() polling
  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 100) { clearInterval(interval); return 100; }
        // Realistic-feeling variable speed
        const speed = p < 70 ? 1.4 : p < 90 ? 0.7 : 0.3;
        return Math.min(p + speed, 100);
      });
    }, 80);
    return () => clearInterval(interval);
  }, []);

  const pct         = Math.round(progress);
  const done        = pct >= 100;
  const currentStep = Math.min(
    Math.floor((pct / 100) * GENERATION_STEPS.length),
    GENERATION_STEPS.length - 1,
  );

  return (
    <div style={{
      maxWidth: 680,
      margin:   "60px auto",
      padding:  "0 24px",
    }}>
      <Card className="fade-up" style={{ padding: "40px 36px" }}>

        {/* ── Header ── */}
        <div style={{
          display:       "flex",
          justifyContent:"space-between",
          alignItems:    "flex-start",
          marginBottom:  10,
        }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ ...textStyles.h2, fontSize: 22, marginBottom: 8 }}>
              {done
                ? "Dein Dossier ist bereit! 🎉"
                : "Dein Dossier wird zusammengebaut…"}
            </h2>
            <p style={{ ...textStyles.body, fontSize: 13 }}>
              {done
                ? "Das professionelle Dossier wurde erfolgreich erstellt und steht zum Download bereit."
                : "Wir erstellen dein professionelles Dossier. Dieser Vorgang kann einige Sekunden dauern. Status: Zusammenstellung läuft."}
            </p>
          </div>

          {!done && (
            <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end", marginBottom: 4 }}>
                <Icon name="checkCircle" size={16} color={colors.teal} />
                <span style={{ ...textStyles.small, color: colors.muted }}>Fortschritt</span>
              </div>
              <span style={{
                fontFamily: "'DM Serif Display', Georgia, serif",
                fontSize:   32,
                color:      colors.dark,
                lineHeight: 1,
              }}>
                {pct}%
              </span>
            </div>
          )}
        </div>

        {/* ── Progress bar ── */}
        <div style={{
          height:       7,
          background:   colors.bg,
          borderRadius: 10,
          overflow:     "hidden",
          marginBottom: 32,
          border:       `1px solid ${colors.border}`,
        }}>
          <div style={{
            height:     "100%",
            width:      `${pct}%`,
            background: done
              ? `linear-gradient(90deg, ${colors.teal}, #48D1BB)`
              : `linear-gradient(90deg, ${colors.orange}, #FF8C5A)`,
            borderRadius: 10,
            transition:   "width .4s ease, background .6s ease",
          }} />
        </div>

        {/* ── Step list ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 36 }}>
          {GENERATION_STEPS.map((label, i) => (
            <StepItem
              key={label}
              label={label}
              index={i}
              current={currentStep}
              done={done}
            />
          ))}
        </div>

        {/* ── Central icon + actions ── */}
        <div style={{
          display:       "flex",
          flexDirection: "column",
          alignItems:    "center",
          gap:           18,
        }}>
          <div style={{
            width:        76,
            height:       76,
            background:   done ? colors.tealLight : colors.orangeLight,
            borderRadius: "50%",
            display:      "flex",
            alignItems:   "center",
            justifyContent: "center",
            transition:   "background .6s ease",
          }}>
            {done
              ? <Icon name="checkCircle" size={36} color={colors.teal} />
              : (
                <div className="spin">
                  <Icon name="file" size={32} color={colors.orange} />
                </div>
              )
            }
          </div>

          <Button
            onClick={() => {}}
            variant={done ? "teal" : "outline"}
            size="lg"
            disabled={!done}
            style={{ minWidth: 220 }}
          >
            <Icon name="download" size={15} color={done ? "#fff" : colors.muted} />
            {done ? "Dossier herunterladen" : "Download Dossier"}
          </Button>

          {done && (
            <div style={{ display: "flex", gap: 12 }}>
              <Button variant="outline" size="sm" onClick={() => setPage("dashboard")}>
                Zum Dashboard
              </Button>
              <Button variant="outline" size="sm">
                <Icon name="mail" size={13} color={colors.mid} />
                Per E-Mail senden
              </Button>
            </div>
          )}
        </div>

      </Card>
    </div>
  );
};
