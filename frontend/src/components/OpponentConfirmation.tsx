import { useState } from "react";
import { colors, textStyles, typography } from "../theme/tokens";
import type { OpponentData, OpponentCategory } from "../types";
import { ALL_CATEGORIES, CATEGORY_META } from "../constants/categoryFields";

// ─────────────────────────────────────────────────────────────────────────────
// OpponentConfirmation – Streitpartei-Bestätigung (US-9.4)
//
// Zeigt KI-Vorschlag für Kategorie (Chips) + Name (Textfeld).
// Nutzer kann Kategorie korrigieren und Namen anpassen.
// ─────────────────────────────────────────────────────────────────────────────

interface OpponentConfirmationProps {
  opponent:  OpponentData;
  onChange:  (category: OpponentCategory, name: string) => void;
}

export const OpponentConfirmation = ({ opponent, onChange }: OpponentConfirmationProps) => {
  const [selectedCategory, setSelectedCategory] = useState<OpponentCategory>(
    (opponent.category as OpponentCategory) ?? "sonstiges"
  );
  const [name, setName] = useState(opponent.name ?? "");

  const handleCategoryChange = (cat: OpponentCategory) => {
    setSelectedCategory(cat);
    setName(""); // Bei Kategoriewechsel Namensfeld leeren (US-9.4)
    onChange(cat, "");
  };

  const handleNameChange = (val: string) => {
    setName(val);
    onChange(selectedCategory, val);
  };

  const needsReview = opponent.needs_review;
  const badgeColor  = needsReview ? colors.orange : colors.teal;
  const badgeBg     = needsReview ? "#FFF7ED"     : colors.tealLight;
  const badgeLabel  = needsReview ? "⚠ Bitte prüfen" : "✓ KI-erkannt";

  return (
    <div>
      {/* Section Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <p style={{ fontFamily: typography.sans, fontSize: 13, fontWeight: 700, color: colors.dark }}>
          Streitpartei
        </p>
        <span style={{
          background: badgeBg,
          color:      badgeColor,
          fontSize:   10,
          fontWeight: 600,
          fontFamily: typography.sans,
          padding:    "2px 8px",
          borderRadius: 50,
          border:     `1px solid ${badgeColor}`,
        }}>
          {badgeLabel}
        </span>
      </div>

      {/* Kategorie-Chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
        {ALL_CATEGORIES.map(cat => {
          const meta    = CATEGORY_META[cat];
          const active  = cat === selectedCategory;
          return (
            <button
              key={cat}
              onClick={() => handleCategoryChange(cat)}
              style={{
                display:      "flex",
                alignItems:   "center",
                gap:          4,
                padding:      "5px 10px",
                borderRadius: 50,
                border:       `2px solid ${active ? colors.orange : colors.border}`,
                background:   active ? colors.orangeLight : colors.white,
                color:        active ? colors.orange : colors.mid,
                fontSize:     12,
                fontFamily:   typography.sans,
                fontWeight:   active ? 700 : 400,
                cursor:       "pointer",
                transition:   "all .15s",
              }}
            >
              <span>{meta.emoji}</span>
              <span>{meta.label}</span>
            </button>
          );
        })}
      </div>

      {/* Namensfeld */}
      <div>
        <p style={{ ...textStyles.small, marginBottom: 4 }}>
          Name der Streitpartei
        </p>
        <input
          value={name}
          onChange={e => handleNameChange(e.target.value)}
          placeholder={CATEGORY_META[selectedCategory].placeholder}
          style={{
            width:        "100%",
            padding:      "10px 14px",
            border:       `1.5px solid ${name ? colors.teal : colors.border}`,
            borderRadius: 8,
            fontSize:     13,
            fontFamily:   typography.sans,
            color:        colors.dark,
            outline:      "none",
            background:   colors.bg,
            boxSizing:    "border-box",
          }}
        />
        {opponent.name && (
          <p style={{ fontSize: 10, color: colors.teal, marginTop: 3, fontFamily: typography.sans }}>
            ✓ KI-Vorschlag: {opponent.name}
          </p>
        )}
      </div>
    </div>
  );
};
