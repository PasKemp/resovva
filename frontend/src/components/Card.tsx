import type { CSSProperties, ReactNode } from "react";
import { colors, radii, shadows } from ".././theme/tokens";

// ─────────────────────────────────────────────────────────────────────────────
// Card — base surface container
// ─────────────────────────────────────────────────────────────────────────────

interface CardProps {
  children:   ReactNode;
  style?:     CSSProperties;
  className?: string;
  hoverable?: boolean;
  onClick?:   () => void;
}

export const Card = ({ children, style, className, hoverable, onClick }: CardProps) => (
  <div
    className={[hoverable ? "card-hover" : "", className].filter(Boolean).join(" ")}
    onClick={onClick}
    style={{
      background:   colors.white,
      borderRadius: radii.lg,
      border:       `1px solid ${colors.border}`,
      padding:      24,
      boxShadow:    shadows.card,
      ...style,
    }}
  >
    {children}
  </div>
);
