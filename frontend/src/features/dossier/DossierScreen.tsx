import { useState, useEffect, useRef, useCallback } from "react";
import { colors, textStyles, typography } from "../../theme/tokens";
import { Button, Card, Icon } from "../../components";
import { dossierApi } from "../../services/api";
import type { DossierGenerationStatus } from "../../services/api";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// DossierScreen — US-6.4 / US-6.5
// Pollt GET /cases/{caseId}/dossier/status alle 3s und zeigt den Fortschritt.
// ─────────────────────────────────────────────────────────────────────────────

const GENERATION_STEPS = [
  "Dokumente prüfen",
  "Chronologie erstellen",
  "Anlagen nummerieren",
  "PDF generieren",
  "Qualitätskontrolle",
] as const;

const POLL_INTERVAL_MS = 3000;

// ── Sub-components ─────────────────────────────────────────────────────────

interface StepItemProps {
  label:   string;
  index:   number;
  current: number;
  done:    boolean;
  error:   boolean;
}

const StepItem = ({ label, index, current, done, error }: StepItemProps) => {
  const isActive = index === current && !done && !error;
  const isDone   = index < current || done;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{
        width:        24,
        height:       24,
        borderRadius: "50%",
        background:   error && isActive ? colors.danger
          : isDone  ? colors.teal
          : isActive ? colors.orange : colors.bg,
        border:       `2px solid ${
          error && isActive ? colors.danger
          : isDone  ? colors.teal
          : isActive ? colors.orange : colors.border
        }`,
        display:      "flex",
        alignItems:   "center",
        justifyContent: "center",
        flexShrink:   0,
        transition:   "all .4s ease",
      }}>
        {isDone   && <Icon name="check" size={12} color="#fff" />}
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

// ── Fortschritts-Mapping: Status → 0-100 ──────────────────────────────────

function statusToPercent(status: DossierGenerationStatus): number {
  switch (status) {
    case "PAID":               return 5;
    case "GENERATING_DOSSIER": return 55;  // Animiert weiter nach oben
    case "COMPLETED":          return 100;
    case "ERROR_GENERATION":   return 0;
    default:                   return 0;
  }
}

// ── DossierScreen ───────────────────────────────────────────────────────────

interface DossierScreenProps extends WithSetPage {
  caseId?: string;
}

export const DossierScreen = ({ setPage, caseId }: DossierScreenProps) => {
  const [status,    setStatus]    = useState<DossierGenerationStatus>("GENERATING_DOSSIER");
  const [progress,  setProgress]  = useState(5);
  const [errorMsg,  setErrorMsg]  = useState<string | null>(null);
  const [pollError, setPollError] = useState(false);

  const intervalRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const animFrameRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  const done  = status === "COMPLETED";
  const error = status === "ERROR_GENERATION";

  // ── Smooth-Animation: Progress bis zum Zielwert schieben ──────────────────
  const animateToTarget = useCallback((target: number) => {
    if (animFrameRef.current) clearInterval(animFrameRef.current);
    animFrameRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev >= target) {
          if (animFrameRef.current) clearInterval(animFrameRef.current);
          return target;
        }
        const speed = prev < 70 ? 1.2 : prev < 90 ? 0.6 : 0.2;
        return Math.min(prev + speed, target);
      });
    }, 80);
  }, []);

  // ── Polling ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!caseId) {
      // Kein caseId → Demo-Modus mit Fake-Animation
      animateToTarget(100);
      return;
    }

    const poll = async () => {
      try {
        const res = await dossierApi.status(caseId);
        setStatus(res.status);
        setPollError(false);

        const target = statusToPercent(res.status);

        if (res.status === "GENERATING_DOSSIER") {
          // Während Generierung: langsam von 10 bis 90 simulieren
          setProgress(prev => {
            const next = prev < 90 ? prev + 0.8 : prev;
            return next;
          });
        } else {
          animateToTarget(target);
        }

        if (res.status === "ERROR_GENERATION") {
          setErrorMsg(res.error_message ?? "Unbekannter Fehler. Bitte kontaktiere den Support.");
        }

        // Polling stoppen wenn fertig oder Fehler
        if (res.status === "COMPLETED" || res.status === "ERROR_GENERATION") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {
        setPollError(true);
      }
    };

    poll(); // Sofort beim Mount
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (animFrameRef.current) clearInterval(animFrameRef.current);
    };
  }, [caseId, animateToTarget]);

  // ── Wenn kein caseId: Fake-Progress als Fallback ───────────────────────────
  useEffect(() => {
    if (caseId) return;
    const t = setInterval(() => {
      setProgress(p => {
        if (p >= 100) { clearInterval(t); setStatus("COMPLETED"); return 100; }
        const speed = p < 70 ? 1.4 : p < 90 ? 0.7 : 0.3;
        return Math.min(p + speed, 100);
      });
    }, 80);
    return () => clearInterval(t);
  }, [caseId]);

  const pct         = Math.round(Math.min(progress, 100));
  const currentStep = Math.min(
    Math.floor((pct / 100) * GENERATION_STEPS.length),
    GENERATION_STEPS.length - 1,
  );

  const handleDownload = () => {
    if (!caseId) return;
    dossierApi.download(caseId);
  };

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
              {done  ? "Dein Dossier ist bereit! 🎉"
               : error ? "Fehler bei der Dossier-Erstellung"
               : "Dein Dossier wird zusammengebaut…"}
            </h2>
            <p style={{ ...textStyles.body, fontSize: 13 }}>
              {done  ? "Das professionelle Dossier wurde erfolgreich erstellt und steht zum Download bereit."
               : error ? (errorMsg ?? "Es ist ein Fehler aufgetreten. Bitte kontaktiere den Support.")
               : pollError ? "Verbindungsproblem – Polling wird fortgesetzt…"
               : "Wir erstellen dein professionelles Dossier. Dieser Vorgang kann ca. 30 Sekunden dauern."}
            </p>
          </div>

          {!done && !error && (
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
        {!error && (
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
        )}

        {/* ── Error-Box ── */}
        {error && (
          <div style={{
            background:   "#FEF2F2",
            border:       `1px solid ${colors.dangerBorder ?? "#FECACA"}`,
            borderRadius: 10,
            padding:      "14px 18px",
            marginBottom: 28,
          }}>
            <p style={{ fontFamily: typography.sans, fontSize: 13, color: colors.danger, lineHeight: 1.6 }}>
              {errorMsg ?? "Unbekannter Fehler bei der Dossier-Generierung."}
            </p>
            <p style={{ fontFamily: typography.sans, fontSize: 12, color: colors.muted, marginTop: 6 }}>
              Bitte kontaktiere unseren Support unter <strong>support@resovva.de</strong> mit deiner Fall-ID.
            </p>
          </div>
        )}

        {/* ── Step list ── */}
        {!error && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 36 }}>
            {GENERATION_STEPS.map((label, i) => (
              <StepItem
                key={label}
                label={label}
                index={i}
                current={currentStep}
                done={done}
                error={error}
              />
            ))}
          </div>
        )}

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
            background:   done   ? colors.tealLight
              : error ? "#FEF2F2"
              : colors.orangeLight,
            borderRadius: "50%",
            display:      "flex",
            alignItems:   "center",
            justifyContent: "center",
            transition:   "background .6s ease",
          }}>
            {done
              ? <Icon name="checkCircle" size={36} color={colors.teal} />
              : error
              ? <Icon name="x" size={32} color={colors.danger} />
              : (
                <div className="spin">
                  <Icon name="file" size={32} color={colors.orange} />
                </div>
              )
            }
          </div>

          {!error && (
            <Button
              onClick={handleDownload}
              variant={done ? "teal" : "outline"}
              size="lg"
              disabled={!done || !caseId}
              style={{ minWidth: 220 }}
            >
              <Icon name="download" size={15} color={done ? "#fff" : colors.muted} />
              {done ? "Dossier herunterladen" : "Download Dossier"}
            </Button>
          )}

          {done && (
            <div style={{ display: "flex", gap: 12 }}>
              <Button variant="outline" size="sm" onClick={() => setPage("dashboard")}>
                Zum Dashboard
              </Button>
            </div>
          )}

          {error && (
            <Button variant="outline" size="sm" onClick={() => setPage("dashboard")}>
              Zurück zum Dashboard
            </Button>
          )}
        </div>

      </Card>
    </div>
  );
};
