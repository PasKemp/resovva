import type { ReactNode } from "react";
import { colors, typography } from "../theme/tokens";

// ─────────────────────────────────────────────────────────────────────────────
// Badge — status / label pill
// ─────────────────────────────────────────────────────────────────────────────

export type BadgeColor = "orange" | "teal" | "yellow" | "green" | "muted" | "red" | "blue" | "purple";

export interface BadgeProps {
  children: ReactNode;
  color?:   BadgeColor;
}

const COLOR_MAP: Record<BadgeColor, { bg: string; text: string }> = {
  orange: { bg: colors.orangeLight, text: colors.orange },
  teal:   { bg: colors.tealLight,   text: colors.teal },
  yellow: { bg: colors.yellow,      text: colors.yellowText },
  green:  { bg: colors.green,       text: colors.greenText },
  red:    { bg: colors.red,         text: colors.redText },
  muted:  { bg: "#F5EFE6",          text: colors.muted },
  blue:   { bg: "#EFF6FF",          text: "#1D4ED8" },
  purple: { bg: "#F5F3FF",          text: "#7C3AED" },
};

/**
 * Status-Badge / Label-Pill für Statusanzeigen und Kennzeichnungen.
 *
 * @param children - Anzeigetext des Badges
 * @param color    - Farbschema (Standard: "muted")
 *
 * @example
 * <Badge color="teal">Abgeschlossen</Badge>
 * <Badge color="orange">Entwurf</Badge>
 */
export const Badge = ({ children, color = "muted" }: BadgeProps) => {
  const { bg, text } = COLOR_MAP[color];
  return (
    <span
      style={{
        background: bg,
        color: text,
        padding: "3px 12px",
        borderRadius: 20,
        fontSize: 12,
        fontWeight: 600,
        fontFamily: typography.sans,
        display: "inline-block",
        lineHeight: 1.6,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
};
