// ─────────────────────────────────────────────────────────────────────────────
// Design Tokens — single source of truth for the entire Resovva UI
// ─────────────────────────────────────────────────────────────────────────────

export const colors = {
  // Brand
  orange: "#F15A24",
  orangeHover: "#D94E1A",
  orangeLight: "#FEF0EB",
  teal: "#2BB5A0",
  tealLight: "#E8F7F5",

  // Neutral
  dark: "#1A1A2E",
  mid: "#4A4A6A",
  muted: "#8A8AAA",
  border: "#f5efe6e0",
  bg: "#F5EFE6",
  white: "#FFFFFF",

  // Semantic
  yellow: "#FFF3CD",
  yellowBorder: "#FFCA28",
  yellowText: "#92400E",
  green: "#E8F5E9",
  greenText: "#2E7D32",
  red: "#FFEBEE",
  redText: "#C62828",
} as const;

export const typography = {
  display: "'DM Serif Display', Georgia, serif",
  sans: "'Plus Jakarta Sans', sans-serif",
} as const;

export const radii = {
  sm: 6,
  md: 10,
  lg: 12,
  xl: 16,
  pill: 50,
  full: 9999,
} as const;

export const shadows = {
  card: "0 2px 12px rgba(0,0,0,.06)",
  modal: "0 16px 64px rgba(0,0,0,.10)",
  hover: "0 8px 32px rgba(0,0,0,.10)",
} as const;

// Reusable text-style objects (use with spread in inline styles)
export const textStyles = {
  h1: {
    fontFamily: typography.display,
    fontSize: 42,
    fontWeight: 400,
    color: colors.dark,
    lineHeight: 1.15,
  },
  h2: {
    fontFamily: typography.display,
    fontSize: 28,
    fontWeight: 400,
    color: colors.dark,
  },
  h3: {
    fontFamily: typography.sans,
    fontSize: 18,
    fontWeight: 700,
    color: colors.dark,
  },
  body: {
    fontFamily: typography.sans,
    fontSize: 14,
    color: colors.mid,
    lineHeight: 1.6,
  },
  small: {
    fontFamily: typography.sans,
    fontSize: 12,
    color: colors.muted,
  },
  label: {
    fontFamily: typography.sans,
    fontSize: 12,
    fontWeight: 600,
    color: colors.muted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
  },
} as const;
