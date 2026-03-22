import { useState } from "react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon } from "../../../components";
import type { UploadedFile } from "../../../types";

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 — Upload & Mobile Scan
// ─────────────────────────────────────────────────────────────────────────────

const INITIAL_FILES: UploadedFile[] = [
  { name: "Stromrechnung_Mrz2026.pdf",  size: "22 MB",   date: "12.03.2026" },
  { name: "Zählerstand_01-03.jpg",       size: "11 MB",   date: "11.03.2026" },
  { name: "Kundenbrief_Jan2026.pdf",     size: "900 KB",  date: "10.03.2026" },
];

interface UploadStepProps {
  onNext: () => void;
}

export const UploadStep = ({ onNext }: UploadStepProps) => {
  const [files,    setFiles]    = useState<UploadedFile[]>(INITIAL_FILES);
  const [dragging, setDragging] = useState(false);

  const removeFile = (index: number) =>
    setFiles(prev => prev.filter((_, i) => i !== index));

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>1. Upload & Mobile Scan</h3>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* ── Drop zone ── */}
          <div
            onDragOver={e  => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); }}
            style={{
              border:       `2px dashed ${dragging ? colors.orange : colors.border}`,
              borderRadius: 12,
              padding:      "36px 20px",
              display:      "flex",
              flexDirection:"column",
              alignItems:   "center",
              justifyContent: "center",
              gap:          14,
              background:   dragging ? colors.orangeLight : colors.bg,
              transition:   "all .2s ease",
              cursor:       "pointer",
            }}
          >
            <div style={{
              width: 60, height: 60,
              background:   colors.orangeLight,
              borderRadius: 14,
              display:      "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon name="upload" size={28} color={colors.orange} />
            </div>
            <p style={{ ...textStyles.body, fontSize: 13, textAlign: "center", color: colors.muted }}>
              Ziehe PDFs hierher oder klicke zum Hochladen
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <Button size="sm">
                <Icon name="scan" size={13} color="#fff" /> Mit dem Handy scannen
              </Button>
              <Button variant="outline" size="sm">
                Datei auswählen
              </Button>
            </div>
          </div>

          {/* ── File list ── */}
          <div>
            <p style={{ ...textStyles.label, marginBottom: 12 }}>Hochgeladene Dateien</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {files.map((f, i) => (
                <div
                  key={f.name}
                  style={{
                    background:   colors.bg,
                    border:       `1px solid ${colors.border}`,
                    borderRadius: 8,
                    padding:      "10px 12px",
                    display:      "flex",
                    alignItems:   "center",
                    gap:          10,
                  }}
                >
                  <div style={{
                    width: 30, height: 30,
                    background:   colors.orangeLight,
                    borderRadius: 7,
                    display:      "flex", alignItems: "center", justifyContent: "center",
                    flexShrink:   0,
                  }}>
                    <Icon name="file" size={14} color={colors.orange} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{
                      fontSize:     12,
                      fontWeight:   600,
                      color:        colors.dark,
                      fontFamily:   typography.sans,
                      overflow:     "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace:   "nowrap",
                    }}>
                      {f.name}
                    </p>
                    <p style={textStyles.small}>{f.size} · {f.date}</p>
                  </div>

                  <div style={{ display: "flex", gap: 4 }}>
                    <button style={{ background: "none", border: "none", cursor: "pointer", padding: 4, borderRadius: 4 }}>
                      <Icon name="eye" size={14} color={colors.muted} />
                    </button>
                    <button
                      onClick={() => removeFile(i)}
                      style={{ background: "none", border: "none", cursor: "pointer", padding: 4, borderRadius: 4 }}
                    >
                      <Icon name="x" size={14} color={colors.muted} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button onClick={onNext} size="lg">
          Weiter zur Analyse <Icon name="arrow" size={15} color="#fff" />
        </Button>
      </div>
    </div>
  );
};
