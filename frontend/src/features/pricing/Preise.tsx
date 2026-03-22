import { colors, textStyles } from "../../theme/tokens";
import { Button, Icon } from "../../components";
import type { WithSetPage } from "../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Pricing Page
// ─────────────────────────────────────────────────────────────────────────────

interface PricingTier {
  title:     string;
  price:     string;
  subtitle:  string;
  features:  string[];
  cta:       string;
  highlight: boolean;
}

const TIERS: PricingTier[] = [
  {
    title:    "Kostenlose Prüfung",
    price:    "0 €",
    subtitle: "Kostenlos starten",
    features: [
      "Dokumente hochladen",
      "KI-Analyse & Anonymisierung",
      "Chronologie-Vorschau",
      "Gap-Analyse",
    ],
    cta:       "Kostenlos starten",
    highlight: false,
  },
  {
    title:    "Vollständiges Dossier",
    price:    "20 €",
    subtitle: "Einmalzahlung · Kein Abo",
    features: [
      "Alles aus kostenlos",
      "Professionelles PDF-Dossier",
      "Nummerierte Anlagen",
      "Versandfertig für Anwalt",
      "30 Tage Zugang",
    ],
    cta:       "Jetzt bestellen",
    highlight: true,
  },
  {
    title:    "Anwaltsvermittlung",
    price:    "Auf Anfrage",
    subtitle: "Persönliche Beratung",
    features: [
      "Alles aus Dossier",
      "Direktvermittlung",
      "Erstberatung inklusive",
      "Erfolgshonorar möglich",
    ],
    cta:       "Kontakt aufnehmen",
    highlight: false,
  },
];

// ── PricingCard ────────────────────────────────────────────────────────────

const PricingCard = ({
  tier,
  onCta,
}: { tier: PricingTier; onCta: () => void }) => (
  <div
    className={tier.highlight ? "" : "card-hover"}
    style={{
      background:   tier.highlight ? colors.dark : colors.white,
      border:       `2px solid ${tier.highlight ? colors.orange : colors.border}`,
      borderRadius: 16,
      padding:      "36px 28px",
      display:      "flex",
      flexDirection:"column",
      position:     "relative",
      overflow:     "hidden",
    }}
  >
    {tier.highlight && (
      <div style={{
        position:   "absolute",
        top:        16,
        right:      -28,
        background: colors.orange,
        color:      "#fff",
        fontSize:   11,
        fontWeight: 700,
        padding:    "4px 36px",
        transform:  "rotate(45deg)",
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        letterSpacing: "0.06em",
      }}>
        BELIEBT
      </div>
    )}

    <p style={{
      ...textStyles.label,
      color:        tier.highlight ? colors.orange : colors.muted,
      marginBottom: 14,
    }}>
      {tier.title}
    </p>

    <div style={{
      fontFamily:   "'DM Serif Display', Georgia, serif",
      fontSize:     tier.price.length > 5 ? 28 : 44,
      color:        tier.highlight ? "#fff" : colors.dark,
      marginBottom: 4,
      lineHeight:   1,
    }}>
      {tier.price}
    </div>
    <p style={{
      fontSize:     12,
      color:        tier.highlight ? "rgba(255,255,255,.45)" : colors.muted,
      fontFamily:   "'Plus Jakarta Sans', sans-serif",
      marginBottom: 28,
    }}>
      {tier.subtitle}
    </p>

    <div style={{ display: "flex", flexDirection: "column", gap: 11, flex: 1, marginBottom: 28 }}>
      {tier.features.map(f => (
        <div key={f} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Icon name="check" size={14} color={tier.highlight ? colors.teal : colors.teal} />
          <span style={{
            fontSize:   13,
            color:      tier.highlight ? "rgba(255,255,255,.75)" : colors.mid,
            fontFamily: "'Plus Jakarta Sans', sans-serif",
          }}>
            {f}
          </span>
        </div>
      ))}
    </div>

    <Button
      onClick={onCta}
      variant={tier.highlight ? "primary" : "outline"}
      size="md"
      style={{ width: "100%", justifyContent: "center" }}
    >
      {tier.cta}
    </Button>
  </div>
);

// ── Preise (Pricing) ────────────────────────────────────────────────────────

export const Preise = ({ setPage }: WithSetPage) => (
  <div style={{ maxWidth: 960, margin: "64px auto", padding: "0 32px" }}>

    {/* Header */}
    <div style={{ textAlign: "center", marginBottom: 52 }}>
      <p style={{ ...textStyles.label, color: colors.orange, marginBottom: 12 }}>
        PREISE
      </p>
      <h1 style={{ ...textStyles.h1, fontSize: 38, marginBottom: 14 }}>
        Transparent. Fair. Einmalig.
      </h1>
      <p style={{ ...textStyles.body, fontSize: 15, maxWidth: 460, margin: "0 auto" }}>
        Keine Abofallen. Erleben Sie den Wert kostenlos –
        zahlen Sie nur für das fertige Dossier.
      </p>
    </div>

    {/* Tier grid */}
    <div style={{
      display:             "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap:                 24,
      alignItems:          "start",
    }}>
      {TIERS.map(tier => (
        <PricingCard
          key={tier.title}
          tier={tier}
          onCta={() => setPage("case")}
        />
      ))}
    </div>

    {/* Footer note */}
    <p style={{
      ...textStyles.small,
      textAlign:  "center",
      marginTop:  40,
      color:      colors.muted,
    }}>
      Alle Preise inkl. MwSt. · Sichere Zahlung via Stripe ·
      DSGVO-konform · 14 Tage Widerrufsrecht
    </p>
  </div>
);
