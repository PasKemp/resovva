// ─────────────────────────────────────────────────────────────────────────────
// Kategorie-Feld-Konfiguration (US-9.5)
//
// Definiert welche Felder für welche Streitpartei-Kategorie relevant sind.
// Irrelevante Felder werden im Bestätigungs-Panel ausgeblendet.
// ─────────────────────────────────────────────────────────────────────────────

import type { OpponentCategory } from "../types";

export interface CategoryMeta {
  label:       string;
  emoji:       string;
  placeholder: string;   // Platzhalter für das Namensfeld
}

export interface FieldConfig {
  malo_id:          boolean;
  meter_number:     boolean;
  dispute_amount:   boolean;
  contract_number:  boolean;
  insurance_number: boolean;
}

export const CATEGORY_META: Record<OpponentCategory, CategoryMeta> = {
  strom:                { label: "Strom",               emoji: "⚡", placeholder: "z.B. Stadtwerke Köln, E.ON…" },
  gas:                  { label: "Gas",                 emoji: "🔥", placeholder: "z.B. Stadtwerke München, Eon…" },
  wasser:               { label: "Wasser",              emoji: "💧", placeholder: "z.B. Stadtwerke Berlin…" },
  versicherung:         { label: "Versicherung",        emoji: "🛡️", placeholder: "z.B. Allianz, AOK, TK…" },
  mobilfunk_internet:   { label: "Mobilfunk/Internet",  emoji: "📱", placeholder: "z.B. Telekom, Vodafone, 1&1…" },
  amt_behoerde:         { label: "Amt/Behörde",         emoji: "🏛️", placeholder: "z.B. Finanzamt, Jobcenter…" },
  vermieter_immobilien: { label: "Vermieter",           emoji: "🏠", placeholder: "z.B. Vonovia, Hausverwaltung…" },
  sonstiges:            { label: "Sonstiges",           emoji: "📋", placeholder: "Name der Gegenseite…" },
};

export const CATEGORY_FIELDS: Record<OpponentCategory, FieldConfig> = {
  strom:                { malo_id: true,  meter_number: true,  dispute_amount: true,  contract_number: false, insurance_number: false },
  gas:                  { malo_id: true,  meter_number: true,  dispute_amount: true,  contract_number: false, insurance_number: false },
  wasser:               { malo_id: true,  meter_number: true,  dispute_amount: true,  contract_number: false, insurance_number: false },
  versicherung:         { malo_id: false, meter_number: false, dispute_amount: true,  contract_number: true,  insurance_number: true  },
  mobilfunk_internet:   { malo_id: false, meter_number: false, dispute_amount: true,  contract_number: true,  insurance_number: false },
  amt_behoerde:         { malo_id: false, meter_number: false, dispute_amount: true,  contract_number: true,  insurance_number: false },
  vermieter_immobilien: { malo_id: false, meter_number: false, dispute_amount: true,  contract_number: true,  insurance_number: false },
  sonstiges:            { malo_id: false, meter_number: false, dispute_amount: true,  contract_number: true,  insurance_number: false },
};

export const ALL_CATEGORIES: OpponentCategory[] = [
  "strom", "gas", "wasser", "versicherung",
  "mobilfunk_internet", "amt_behoerde", "vermieter_immobilien", "sonstiges",
];

/** Kategorien für die ein MaStR-Lookup sinnvoll ist. */
export const ENERGY_CATEGORIES: Set<OpponentCategory> = new Set(["strom", "gas", "wasser"]);

/** Feld-Labels und Platzhalter für alle extrahierten Felder. */
export const FIELD_LABELS_MAP: Record<string, { label: string; placeholder: string }> = {
  malo_id:          { label: "Marktlokations-ID (MaLo)", placeholder: "DE…" },
  meter_number:     { label: "Zählernummer",              placeholder: "Z123456…" },
  dispute_amount:   { label: "Streitbetrag (€)",          placeholder: "274.50" },
  contract_number:  { label: "Vertragsnummer",            placeholder: "VN-…" },
  insurance_number: { label: "Versicherungsnummer",       placeholder: "VS-…" },
};
