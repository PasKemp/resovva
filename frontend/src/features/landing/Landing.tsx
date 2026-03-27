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
    step: "2", icon: "shield" as const,
    title: "Automatische Analyse",
    desc:  "Lokaler Schutz. Deine sensiblen Daten (z.B. IBAN) werden auf unseren Servern vor der KI-Analyse automatisch geschwärzt.",
    delay: "0.12s",
  },
  {
    step: "3", icon: "download" as const,
    title: "Dossier erhalten",
    desc:  "Erhalte ein rechtssicheres Dossier zum Download oder Versand an einen Anwalt.",
    delay: "0.20s",
  },
] as const;

// ── Sub-components ─────────────────────────────────────────────────────────

const HeroIllustration = () => (
  <div style={{
    background:    "linear-gradient(135deg, #EEF4FF 0%, #E4F5F0 100%)",
    height:        290,
    display:       "flex",
    alignItems:    "center",
    justifyContent:"center",
    position:      "relative",
    overflow:      "hidden",
  }}>
    <svg viewBox="0 0 320 240" style={{ width: "100%", height: "100%", padding: 24 }}>
      {/* Subtle dot grid */}
      {[40, 80, 120, 160, 200].map(y =>
        [40, 80, 120, 160, 200, 240, 280].map(x => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.5" fill="#C8D8E8" />
        ))
      )}
      {/* Outer glow ring */}
      <circle cx="160" cy="120" r="88" stroke={colors.teal} strokeWidth="1" fill="none" strokeOpacity=".18" />
      <circle cx="160" cy="120" r="72" stroke={colors.teal} strokeWidth="1" fill="none" strokeOpacity=".12" />
      {/* Shield body */}
      <path
        d="M160 30 L208 52 L208 112 C208 148 184 174 160 184 C136 174 112 148 112 112 L112 52 Z"
        fill={colors.teal}
        fillOpacity=".12"
        stroke={colors.teal}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {/* Shield inner accent */}
      <path
        d="M160 45 L198 63 L198 112 C198 142 178 164 160 172 C142 164 122 142 122 112 L122 63 Z"
        fill={colors.teal}
        fillOpacity=".08"
        stroke={colors.teal}
        strokeWidth="1"
        strokeLinejoin="round"
      />
      {/* Lock body */}
      <rect x="148" y="112" width="24" height="20" rx="3" fill={colors.teal} fillOpacity=".85" />
      {/* Lock shackle */}
      <path d="M153 112 L153 104 A7 7 0 0 1 167 104 L167 112" stroke={colors.teal} strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {/* Lock keyhole */}
      <circle cx="160" cy="121" r="3" fill="#fff" fillOpacity=".9" />
      <rect x="158.5" y="121" width="3" height="5" rx="1" fill="#fff" fillOpacity=".9" />
      {/* Checkmark in upper shield */}
      <path d="M150 88 L157 96 L172 78" stroke={colors.orange} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      {/* Floating data nodes */}
      <circle cx="80"  cy="80"  r="6" fill={colors.orange} fillOpacity=".25" stroke={colors.orange} strokeWidth="1.5" />
      <circle cx="240" cy="80"  r="6" fill={colors.teal}   fillOpacity=".25" stroke={colors.teal}   strokeWidth="1.5" />
      <circle cx="72"  cy="150" r="4" fill={colors.teal}   fillOpacity=".3"  stroke={colors.teal}   strokeWidth="1" />
      <circle cx="248" cy="155" r="4" fill={colors.orange} fillOpacity=".3"  stroke={colors.orange} strokeWidth="1" />
      <circle cx="104" cy="188" r="3" fill={colors.teal}   fillOpacity=".4"  stroke={colors.teal}   strokeWidth="1" />
      <circle cx="216" cy="188" r="3" fill={colors.orange} fillOpacity=".4"  stroke={colors.orange} strokeWidth="1" />
      {/* Connector lines to shield */}
      <line x1="86"  y1="83"  x2="114" y2="95"  stroke={colors.teal}   strokeWidth="1" strokeOpacity=".35" strokeDasharray="4,3" />
      <line x1="234" y1="83"  x2="206" y2="95"  stroke={colors.orange} strokeWidth="1" strokeOpacity=".35" strokeDasharray="4,3" />
      <line x1="76"  y1="146" x2="114" y2="130" stroke={colors.teal}   strokeWidth="1" strokeOpacity=".3"  strokeDasharray="4,3" />
      <line x1="244" y1="151" x2="206" y2="130" stroke={colors.orange} strokeWidth="1" strokeOpacity=".3"  strokeDasharray="4,3" />
      {/* DSGVO label badge */}
      <rect x="126" y="192" width="68" height="22" rx="11" fill={colors.teal} fillOpacity=".15" stroke={colors.teal} strokeWidth="1" />
      <text x="160" y="207" textAnchor="middle" fontSize="9" fontWeight="600" fill={colors.teal} fontFamily="'Plus Jakarta Sans', sans-serif">
        DSGVO-konform
      </text>
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
          <Button variant="ghost" size="lg">
            Mehr erfahren
          </Button>
        </div>

        <div style={{ display: "flex", gap: 22, flexWrap: "wrap" }}>
          {TRUST_BADGES.map(({ icon, label }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <Icon name="shield" size={16} color={colors.teal} />
              <Icon name={icon} size={18} color={colors.teal} />
              <span style={{ ...textStyles.label, color: colors.teal, textTransform: "none", letterSpacing: 0, fontSize: 13 }}>
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
            KI-gestützte Analyse mit automatischem DSGVO-Schutz
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
            <Icon name={icon} size={24} color={colors.teal} />   {/* US-7.2: 19 → 24px */}
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
        Jetzt Fall kostenlos prüfen&nbsp;
        <Icon name="arrow" size={16} color="#fff" />
      </Button>
    </div>
  </div>
);
