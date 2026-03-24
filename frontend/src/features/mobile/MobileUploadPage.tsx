import { useEffect, useRef, useState } from "react";
import imageCompression from "browser-image-compression";
import { colors, textStyles, typography } from "../../theme/tokens";
import { mobileUploadApi } from "../../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// MobileUploadPage — Epic 2 (US-2.3)
//
// Wird auf dem Smartphone aufgerufen nach QR-Code-Scan.
// URL-Schema: /mobile-upload?token=<rawToken>
//
// Flow:
//   1. Token aus URL-Params lesen
//   2. Token-Gültigkeit via GET /api/v1/upload-tokens/{token}/info prüfen
//   3. Nutzer kann Fotos direkt mit der Kamera machen oder aus Galerie wählen
//   4. Bilder werden komprimiert und via POST /api/v1/mobile-upload hochgeladen
//   5. Mehrere Fotos möglich; PC pollt automatisch auf neue Dateien
// ─────────────────────────────────────────────────────────────────────────────

const COMPRESS_OPTIONS = {
  maxSizeMB:        10,
  maxWidthOrHeight: 2000,
  useWebWorker:     true,
  fileType:         "image/jpeg" as const,
  initialQuality:   0.8,
};

type TokenState = "checking" | "valid" | "expired" | "invalid";

interface UploadResult {
  filename: string;
  ok:       boolean;
  error?:   string;
}

export const MobileUploadPage = () => {
  const token = new URLSearchParams(window.location.search).get("token") ?? "";

  const [tokenState, setTokenState] = useState<TokenState>("checking");
  const [uploading,  setUploading]  = useState(false);
  const [results,    setResults]    = useState<UploadResult[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Token beim Mount prüfen
  useEffect(() => {
    if (!token) { setTokenState("invalid"); return; }

    mobileUploadApi.getTokenInfo(token)
      .then(() => setTokenState("valid"))
      .catch((err: Error) => {
        if (err.message.includes("410") || err.message.includes("abgelaufen") || err.message.includes("verwendet")) {
          setTokenState("expired");
        } else {
          setTokenState("invalid");
        }
      });
  }, [token]);

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setUploading(true);

    for (const raw of Array.from(fileList)) {
      const name = raw.name;
      try {
        const compressed = raw.type.startsWith("image/")
          ? await imageCompression(raw, COMPRESS_OPTIONS)
          : raw;

        await mobileUploadApi.uploadFile(token, compressed);
        setResults(prev => [...prev, { filename: name, ok: true }]);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload fehlgeschlagen";
        setResults(prev => [...prev, { filename: name, ok: false, error: msg }]);
      }
    }

    setUploading(false);
  }

  // ── States ─────────────────────────────────────────────────────────────────

  if (tokenState === "checking") {
    return <FullScreenMessage emoji="🔍" text="Token wird geprüft…" muted />;
  }

  if (tokenState === "invalid") {
    return (
      <FullScreenMessage
        emoji="❌"
        text="Ungültiger QR-Code"
        sub="Dieser Link ist nicht gültig. Bitte scanne den QR-Code erneut."
      />
    );
  }

  if (tokenState === "expired") {
    return (
      <FullScreenMessage
        emoji="⏰"
        text="Link abgelaufen"
        sub="Der QR-Code ist abgelaufen (15 Minuten) oder wurde bereits verwendet. Bitte generiere am PC einen neuen."
      />
    );
  }

  // ── Upload-Interface ────────────────────────────────────────────────────────

  return (
    <div style={{
      minHeight:      "100dvh",
      background:     colors.bg,
      display:        "flex",
      flexDirection:  "column",
      alignItems:     "center",
      padding:        "32px 20px 48px",
      fontFamily:     typography.sans,
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div style={{
          width:        72,
          height:       72,
          borderRadius: "50%",
          background:   colors.orangeLight,
          display:      "flex",
          alignItems:   "center",
          justifyContent: "center",
          margin:       "0 auto 16px",
          fontSize:     32,
        }}>
          📷
        </div>
        <h1 style={{ ...textStyles.h3, fontSize: 22, marginBottom: 6 }}>
          Dokument fotografieren
        </h1>
        <p style={{ ...textStyles.body, fontSize: 14, color: colors.muted, maxWidth: 280, margin: "0 auto" }}>
          Mache ein Foto deines Dokuments. Es wird direkt in deinen Fall übertragen.
        </p>
      </div>

      {/* Datei-Input (versteckt) */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf"
        capture="environment"   // Kamera direkt auf Android/iOS
        multiple
        style={{ display: "none" }}
        onChange={e => handleFiles(e.target.files)}
      />

      {/* Kamera-Button */}
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        style={{
          width:          "100%",
          maxWidth:       340,
          padding:        "18px 24px",
          background:     uploading ? colors.muted : colors.orange,
          color:          "#fff",
          border:         "none",
          borderRadius:   14,
          fontSize:       17,
          fontWeight:     700,
          fontFamily:     typography.sans,
          cursor:         uploading ? "default" : "pointer",
          marginBottom:   16,
          transition:     "background .2s",
        }}
      >
        {uploading ? "Wird hochgeladen…" : "📷  Foto aufnehmen / Datei wählen"}
      </button>

      {/* Galerie-Button (ohne capture – für bestehende Bilder) */}
      <button
        onClick={() => {
          if (fileInputRef.current) {
            fileInputRef.current.removeAttribute("capture");
            fileInputRef.current.click();
            // capture nach kurzer Verzögerung wiederherstellen
            setTimeout(() => fileInputRef.current?.setAttribute("capture", "environment"), 500);
          }
        }}
        disabled={uploading}
        style={{
          width:          "100%",
          maxWidth:       340,
          padding:        "14px 24px",
          background:     "transparent",
          color:          colors.orange,
          border:         `2px solid ${colors.orange}`,
          borderRadius:   14,
          fontSize:       15,
          fontWeight:     600,
          fontFamily:     typography.sans,
          cursor:         uploading ? "default" : "pointer",
          marginBottom:   32,
        }}
      >
        🖼  Aus Galerie wählen
      </button>

      {/* Ergebnis-Liste */}
      {results.length > 0 && (
        <div style={{ width: "100%", maxWidth: 340 }}>
          <p style={{ ...textStyles.label, marginBottom: 10 }}>
            Hochgeladene Dokumente
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {results.map((r, i) => (
              <div
                key={i}
                style={{
                  background:   r.ok ? colors.green : colors.red,
                  border:       `1px solid ${r.ok ? colors.greenText : colors.redText}`,
                  borderRadius: 10,
                  padding:      "10px 14px",
                  display:      "flex",
                  alignItems:   "center",
                  gap:          10,
                }}
              >
                <span style={{ fontSize: 18 }}>{r.ok ? "✅" : "❌"}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{
                    fontSize:     13,
                    fontWeight:   600,
                    color:        r.ok ? colors.greenText : colors.redText,
                    overflow:     "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace:   "nowrap",
                  }}>
                    {r.filename}
                  </p>
                  {r.error && (
                    <p style={{ fontSize: 11, color: colors.redText }}>
                      {r.error}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {results.some(r => r.ok) && (
            <p style={{
              ...textStyles.small,
              textAlign:  "center",
              marginTop:  16,
              color:      colors.teal,
            }}>
              ✓ Dokumente wurden übertragen. Du kannst weitere Fotos hinzufügen oder diese Seite schließen.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

// ── Hilfkomponente ──────────────────────────────────────────────────────────

function FullScreenMessage({ emoji, text, sub, muted }: {
  emoji: string;
  text:  string;
  sub?:  string;
  muted?: boolean;
}) {
  return (
    <div style={{
      minHeight:      "100dvh",
      background:     colors.bg,
      display:        "flex",
      flexDirection:  "column",
      alignItems:     "center",
      justifyContent: "center",
      padding:        "24px",
      fontFamily:     typography.sans,
      textAlign:      "center",
    }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>{emoji}</div>
      <p style={{ ...textStyles.h3, color: muted ? colors.muted : colors.dark, marginBottom: 8 }}>
        {text}
      </p>
      {sub && (
        <p style={{ ...textStyles.body, color: colors.muted, maxWidth: 300 }}>
          {sub}
        </p>
      )}
    </div>
  );
}
