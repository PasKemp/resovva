import { colors, textStyles } from "../../theme/tokens";
import { Button, Card, Icon } from "../../components";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Landing Page
// ─────────────────────────────────────────────────────────────────────────────

const TRUST_BADGES = [
  { icon: "shield"  as const, label: "Datensicherheit & DSGVO" },
  { icon: "users"   as const, label: "Juristische Prüfung" },
  { icon: "file"    as const, label: "Professionelles Dossier" },
] as const;

const HOW_IT_WORKS = [
  {
    step: "1", icon: "upload" as const,
    title: "Dokumente hochladen",
    desc:  "PDFs, Rechnungen oder Fotos – ganz einfach per Drag & Drop.",
    delay: "0.05s",
  },
  {
    step: "2", icon: "brain" as const,
    title: "Automatische Analyse",
    desc:  "KI extrahiert relevante Daten und anonymisiert sensible Informationen.",
    delay: "0.12s",
  },
  {
    step: "3", icon: "file" as const,
    title: "Dossier erhalten",
    desc:  "Erhalte ein rechtssicheres Dossier zum Download oder Versand an einen Anwalt.",
    delay: "0.20s",
  },
] as const;

// ── Sub-components ─────────────────────────────────────────────────────────

const HeroIllustration = () => (
  <div style={{
    background:    "linear-gradient(135deg, #F5F0E8 0%, #EDE8DC 100%)",
    height:        290,
    display:       "flex",
    alignItems:    "center",
    justifyContent:"center",
    position:      "relative",
    overflow:      "hidden",
  }}>
    <svg viewBox="0 0 320 240" style={{ width: "100%", height: "100%", padding: 24 }}>
      {/* Background grid */}
      {[40, 80, 120, 160, 200].map(y => (
        <line key={y} x1="0" y1={y} x2="320" y2={y} stroke="#D4C9B0" strokeWidth=".5" strokeDasharray="4,4" />
      ))}
      {[60, 120, 180, 240].map(x => (
        <line key={x} x1={x} y1="0" x2={x} y2="240" stroke="#D4C9B0" strokeWidth=".5" strokeDasharray="4,4" />
      ))}
      {/* Gauges */}
      <circle cx="60"  cy="180" r="30" stroke="#8B7355" strokeWidth="2" fill="none" />
      <path d="M40 190 A20 20 0 0 1 80 190" stroke={colors.orange} strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="260" cy="190" r="25" stroke="#8B7355" strokeWidth="2" fill="none" />
      <path d="M244 200 A16 16 0 0 1 276 200" stroke={colors.teal} strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* Connecting wires */}
      <path d="M90 180 C120 180 120 100 160 100 C200 100 200 180 230 180" stroke="#8B7355" strokeWidth="1.5" fill="none" strokeDasharray="6,3" />
      <path d="M160 100 L160 50" stroke="#8B7355" strokeWidth="1.5" fill="none" />
      {/* Lightbulbs */}
      <circle cx="100" cy="60" r="14" stroke="#8B7355" strokeWidth="1.5" fill="rgba(255,200,50,.3)" />
      <line x1="100" y1="74" x2="100" y2="84" stroke="#8B7355" strokeWidth="1.5" />
      <circle cx="220" cy="60" r="14" stroke="#8B7355" strokeWidth="1.5" fill="rgba(255,200,50,.12)" />
      <line x1="220" y1="74" x2="220" y2="84" stroke="#8B7355" strokeWidth="1.5" />
      {/* Person */}
      <circle cx="160" cy="28" r="9" fill="#8B7355" />
      <path d="M155 37 L155 65 L150 80 M165 37 L165 65 L170 80 M155 50 L165 50" stroke="#8B7355" strokeWidth="2" strokeLinecap="round" fill="none" />
      <rect x="148" y="64" width="7" height="14" rx="2" fill="#3D2B1F" />
      <rect x="163" y="64" width="7" height="14" rx="2" fill="#3D2B1F" />
      {/* Balance scale */}
      <line x1="160" y1="37" x2="160" y2="45" stroke="#5C4033" strokeWidth="1.5" />
      <line x1="140" y1="42" x2="180" y2="42" stroke="#5C4033" strokeWidth="1.5" />
      <line x1="140" y1="42" x2="140" y2="50" stroke="#5C4033" strokeWidth="1" />
      <line x1="180" y1="42" x2="180" y2="50" stroke="#5C4033" strokeWidth="1" />
    </svg>
  </div>
);

// ── Landing ────────────────────────────────────────────────────────────────

export const Landing = ({ setPage }: WithSetPage) => (
  <div>
    {/* ── Hero ── */}
    <div style={{
      maxWidth: 1180, margin: "0 auto",
      padding:  "60px 32px 40px",
      display:  "grid",
      gridTemplateColumns: "1fr 430px",
      gap:      48,
      alignItems: "center",
    }}>
      {/* Hero text card */}
      <Card className="fade-up" style={{ border: `2px solid ${colors.border}`, padding: "48px 40px" }}>
        <p style={{ ...textStyles.label, color: colors.orange, marginBottom: 12 }}>
          ⚡ LEGALTECH FÜR VERBRAUCHER
        </p>
        <h1 style={{ ...textStyles.h1, marginBottom: 18 }}>
          Waffengleichheit im<br />Energie-Dschungel
        </h1>
        <p style={{ ...textStyles.body, marginBottom: 32, maxWidth: 460 }}>
          Resovva hilft Verbrauchern, ihre Rechte gegenüber Netzbetreibern durchzusetzen –
          schnell, transparent und juristisch abgesichert. Lade Dokumente hoch, wir
          analysieren und erstellen ein professionelles Dossier.
        </p>

        <div style={{ display: "flex", gap: 12, marginBottom: 28 }}>
          <Button onClick={() => setPage("case")} size="lg">
            Jetzt Fall kostenlos prüfen
          </Button>
          <Button variant="outline" size="lg">
            Mehr erfahren
          </Button>
        </div>

        <div style={{ display: "flex", gap: 22, flexWrap: "wrap" }}>
          {TRUST_BADGES.map(({ icon, label }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name={icon} size={15} color={colors.teal} />
              <span style={{ ...textStyles.label, color: colors.teal, textTransform: "none", letterSpacing: 0 }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Illustration card */}
      <Card
        className="fade-up"
        style={{ padding: 0, overflow: "hidden", animationDelay: "0.12s" }}
      >
        <HeroIllustration />
        <div style={{ padding: "12px 16px", borderTop: `1px solid ${colors.border}` }}>
          <p style={{ ...textStyles.small, textAlign: "center", color: colors.muted }}>
            Illustration: Waffengleichheit visualisiert – Nutzer gegen den Energie-Dschungel
          </p>
        </div>
      </Card>
    </div>

    {/* ── How it works ── */}
    <div style={{
      maxWidth: 1180, margin: "0 auto",
      padding:  "0 32px 60px",
      display:  "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap:      24,                        // US-7.2: 20 → 24px
    }}>
      {HOW_IT_WORKS.map(({ step, icon, title, desc, delay }) => (
        <Card key={step} hoverable className="fade-up" style={{ animationDelay: delay, minHeight: 180, padding: "28px 24px" }}>
          <div style={{
            width: 48, height: 48,          // US-7.2: 38 → 48px
            background:   colors.orangeLight,
            borderRadius: 12,
            display:      "flex", alignItems: "center", justifyContent: "center",
            marginBottom: 18,
          }}>
            <Icon name={icon} size={24} color={colors.orange} />   {/* US-7.2: 19 → 24px */}
          </div>
          <h3 style={{ ...textStyles.h3, fontSize: 16, marginBottom: 10 }}>
            {step}. {title}
          </h3>
          <p style={{ ...textStyles.body, fontSize: 14 }}>{desc}</p>
        </Card>
      ))}
    </div>

    {/* ── CTA Banner ── */}
    <div style={{ background: colors.dark, padding: "52px 32px", textAlign: "center" }}>
      <h2 style={{ ...textStyles.h2, color: "#fff", marginBottom: 12 }}>
        Bereit, Ihr Recht durchzusetzen?
      </h2>
      <p style={{ ...textStyles.body, color: "rgba(255,255,255,.55)", marginBottom: 28 }}>
        Kostenlos starten. Zahlen Sie nur, wenn das Dossier fertig ist.
      </p>
      <Button onClick={() => setPage("case")} size="lg">
        Jetzt kostenlos beginnen&nbsp;
        <Icon name="arrow" size={16} color="#fff" />
      </Button>
    </div>
  </div>
);
