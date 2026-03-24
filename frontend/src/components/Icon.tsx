import type { CSSProperties } from "react";
import { colors } from "../theme/tokens";

// ─────────────────────────────────────────────────────────────────────────────
// Icon — SVG icon library for Resovva
// ─────────────────────────────────────────────────────────────────────────────

export type IconName =
  | "shield" | "users" | "file" | "upload" | "brain" | "list" | "folder"
  | "plus" | "check" | "warn" | "x" | "eye" | "download" | "search"
  | "scale" | "phone" | "arrow" | "export" | "import" | "template"
  | "activity" | "scan" | "checkCircle" | "spinner" | "mail";

export interface IconProps {
  name:   IconName;
  size?:  number;
  color?: string;
  style?: CSSProperties;
}

const PATHS: Record<IconName, (c: string) => JSX.Element> = {
  shield: c => (
    <path d="M12 2L4 6v5c0 5.25 3.4 10.15 8 11.25C16.6 21.15 20 16.25 20 11V6L12 2z"
      fill={c} fillOpacity=".18" stroke={c} strokeWidth="1.5" />
  ),
  users: c => (<>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <circle cx="9" cy="7" r="4" stroke={c} strokeWidth="1.5" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  file: c => (<>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke={c} strokeWidth="1.5" fill="none" />
    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  upload: c => (<>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <polyline points="17 8 12 3 7 8" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="12" y1="3" x2="12" y2="15" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  brain: c => (<>
    <circle cx="12" cy="12" r="9" stroke={c} strokeWidth="1.5" fill="none" />
    <path d="M9 9h.01M15 9h.01M9 15h6" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  list: c => (
    <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  ),
  folder: c => (
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke={c} strokeWidth="1.5" fill="none" />
  ),
  plus: c => (
    <path d="M12 5v14M5 12h14" stroke={c} strokeWidth="2" strokeLinecap="round" />
  ),
  check: c => (
    <path d="M20 6L9 17l-5-5" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  warn: c => (<>
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke={c} strokeWidth="1.5" fill="none" />
    <line x1="12" y1="9" x2="12" y2="13" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <line x1="12" y1="17" x2="12.01" y2="17" stroke={c} strokeWidth="2" strokeLinecap="round" />
  </>),
  x: c => (
    <path d="M18 6L6 18M6 6l12 12" stroke={c} strokeWidth="2" strokeLinecap="round" />
  ),
  eye: c => (<>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke={c} strokeWidth="1.5" fill="none" />
    <circle cx="12" cy="12" r="3" stroke={c} strokeWidth="1.5" />
  </>),
  download: c => (<>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <polyline points="7 10 12 15 17 10" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="12" y1="15" x2="12" y2="3" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  search: c => (<>
    <circle cx="11" cy="11" r="8" stroke={c} strokeWidth="1.5" />
    <path d="M21 21l-4.35-4.35" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  scale: c => (<>
    <path d="M12 3v18M8 7H4l-2 5h6l-2-5zM20 7h-4l-2 5h6l-2-5z" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    <path d="M4 21h16" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  phone: c => (
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3 2.18h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21 16.92z" stroke={c} strokeWidth="1.5" fill="none" />
  ),
  arrow: c => (
    <path d="M5 12h14M12 5l7 7-7 7" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  export: c => (<>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <polyline points="17 8 12 3 7 8" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="12" y1="15" x2="12" y2="3" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  import: c => (<>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <polyline points="7 10 12 15 17 10" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="12" y1="15" x2="12" y2="3" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  template: c => (<>
    <rect x="3" y="3" width="18" height="18" rx="2" stroke={c} strokeWidth="1.5" fill="none" />
    <path d="M3 9h18M9 21V9" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  activity: c => (
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  ),
  scan: c => (<>
    <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
    <line x1="3" y1="12" x2="21" y2="12" stroke={c} strokeWidth="1.5" strokeLinecap="round" />
  </>),
  checkCircle: c => (<>
    <circle cx="12" cy="12" r="9" stroke={c} strokeWidth="1.5" fill="none" />
    <path d="M9 12l2 2 4-4" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </>),
  spinner: c => (
    <circle cx="12" cy="12" r="9" stroke={c} strokeWidth="2.5" fill="none" strokeDasharray="28 56" strokeLinecap="round" />
  ),
  mail: c => (<>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" stroke={c} strokeWidth="1.5" fill="none" />
    <polyline points="22,6 12,13 2,6" stroke={c} strokeWidth="1.5" />
  </>),
};

/**
 * SVG-Icon-Komponente mit 23 eingebauten Icons.
 *
 * @param name  - Icon-Bezeichner aus der `IconName`-Union
 * @param size  - Breite und Höhe in Pixeln (Standard: 16)
 * @param color - SVG-Strichfarbe (Standard: colors.orange)
 * @param style - Zusätzliche Inline-Styles auf dem SVG-Element
 *
 * @example
 * <Icon name="upload" size={24} color="#fff" />
 */
export const Icon = ({ name, size = 16, color = colors.orange, style }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={{ flexShrink: 0, ...style }}
  >
    {PATHS[name]?.(color)}
  </svg>
);
