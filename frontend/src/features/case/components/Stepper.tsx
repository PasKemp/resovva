import React from "react";
import { colors, typography } from "../../../theme/tokens";
import { Icon } from "../../../components";

export interface StepMeta {
  label: string;
  sublabel: string;
  icon: string;
}

export const STEPS: StepMeta[] = [
  { label: "Fall",         sublabel: "Kurzbeschreibung",    icon: "file"   },
  { label: "Upload",       sublabel: "Dokumente & Scan",    icon: "upload" },
  { label: "Analyse",      sublabel: "KI & Datenschutz",    icon: "brain"  },
  { label: "Roter Faden",  sublabel: "Chronologie",         icon: "list"   },
  { label: "Abschluss",    sublabel: "Überblick & Zahlung", icon: "folder" },
];

const StepDot: React.FC<{ index: number; current: number }> = ({ index, current }) => {
  const done   = index < current;
  const active = index === current;
  return (
    <div style={{
      width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
      background: done ? "#27AE60" : active ? colors.orange : colors.bg,
      border: `2px solid ${done ? "#27AE60" : active ? colors.orange : colors.border}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      transition: "all .3s ease",
    }}>
      {done
        ? <Icon name="check" size={16} color="#fff" />
        : <span style={{ fontSize: 13, fontWeight: 700, fontFamily: typography.sans, color: active ? "#fff" : colors.muted }}>
            {index + 1}
          </span>
      }
    </div>
  );
};

interface StepperProps {
  current: number;
  onStep: (i: number) => void;
}

export const Stepper: React.FC<StepperProps> = ({ current, onStep }) => (
  <div style={{
    background: colors.white, borderRadius: 14,
    border: `1px solid ${colors.border}`,
    padding: "16px 28px", marginBottom: 0,
    display: "flex", alignItems: "center", minHeight: 72,
  }}>
    {STEPS.map((step, i) => (
      <div key={i} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : "0 0 auto" }}>
        <div
          onClick={() => i <= current && onStep(i)}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            cursor: i <= current ? "pointer" : "default",
            flexShrink: 0, opacity: i > current ? 0.5 : 1, transition: "opacity .2s",
          }}
        >
          <StepDot index={i} current={current} />
          <div style={{ overflow: "hidden" }}>
            <p style={{
              fontSize: 13, fontWeight: 700, fontFamily: typography.sans, lineHeight: 1.2, whiteSpace: "nowrap",
              color: i < current ? "#27AE60" : i === current ? colors.orange : colors.muted,
            }}>
              {step.label}
            </p>
            <p style={{
              fontSize: 11, fontFamily: typography.sans, lineHeight: 1.3, whiteSpace: "nowrap",
              color: i === current ? colors.mid : colors.muted,
              fontWeight: i === current ? 500 : 400,
            }}>
              {step.sublabel}
            </p>
          </div>
        </div>
        {i < STEPS.length - 1 && (
          <div style={{
            flex: 1, height: 2, minWidth: 16, margin: "0 12px", borderRadius: 2,
            background: i < current ? "#27AE60" : "#E5E7EB",
            transition: "background .4s ease",
          }} />
        )}
      </div>
    ))}
  </div>
);
