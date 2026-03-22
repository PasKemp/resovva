import type { CSSProperties, MouseEvent, ReactNode } from "react";
import { colors, radii, typography } from ".././theme/tokens";

// ─────────────────────────────────────────────────────────────────────────────
// Button
// ─────────────────────────────────────────────────────────────────────────────

export type ButtonVariant = "primary" | "outline" | "teal" | "ghost";
export type ButtonSize    = "sm" | "md" | "lg";

interface ButtonProps {
  children: ReactNode;
  variant?:  ButtonVariant;
  size?:     ButtonSize;
  disabled?: boolean;
  onClick?:  (e: MouseEvent<HTMLButtonElement>) => void;
  style?:    CSSProperties;
  type?:     "button" | "submit" | "reset";
}

const SIZE_STYLES: Record<ButtonSize, CSSProperties> = {
  sm: { padding: "6px 16px",  fontSize: 13 },
  md: { padding: "10px 22px", fontSize: 14 },
  lg: { padding: "13px 30px", fontSize: 15 },
};

const VARIANT_STYLES: Record<ButtonVariant, CSSProperties> = {
  primary: { background: colors.orange,  color: "#fff", border: "none" },
  outline: { background: "transparent",  color: colors.dark, border: `1.5px solid ${colors.border}` },
  teal:    { background: colors.teal,    color: "#fff", border: "none" },
  ghost:   { background: "transparent",  color: colors.mid,  border: "none", padding: "8px 14px" },
};

export const Button = ({
  children,
  variant  = "primary",
  size     = "md",
  disabled = false,
  onClick,
  style,
  type = "button",
}: ButtonProps) => {
  const base: CSSProperties = {
    fontFamily:     typography.sans,
    fontWeight:     600,
    borderRadius:   radii.pill,
    cursor:         disabled ? "not-allowed" : "pointer",
    transition:     "background 0.18s, opacity 0.18s, box-shadow 0.18s",
    display:        "inline-flex",
    alignItems:     "center",
    justifyContent: "center",
    gap:            7,
    opacity:        disabled ? 0.52 : 1,
    lineHeight:     1,
    whiteSpace:     "nowrap",
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{ ...base, ...SIZE_STYLES[size], ...VARIANT_STYLES[variant], ...style }}
      onMouseEnter={e => {
        if (disabled) return;
        const el = e.currentTarget;
        if (variant === "primary") el.style.background = colors.orangeHover;
        if (variant === "teal")    el.style.opacity = "0.88";
        if (variant === "outline") el.style.borderColor = colors.mid;
      }}
      onMouseLeave={e => {
        if (disabled) return;
        const el = e.currentTarget;
        if (variant === "primary") el.style.background = colors.orange;
        if (variant === "teal")    el.style.opacity = "1";
        if (variant === "outline") el.style.borderColor = colors.border;
      }}
    >
      {children}
    </button>
  );
};
