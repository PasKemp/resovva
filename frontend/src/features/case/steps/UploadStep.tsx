import { useEffect, useRef, useState } from "react";
import imageCompression from "browser-image-compression";
import { QRCodeSVG } from "qrcode.react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon } from "../../../components";
import { documentsApi, mobileUploadApi, caseStatusApi } from "../../../services/api";
import type { DocumentsResponse } from "../../../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 — Upload & Mobile Scan
// ─────────────────────────────────────────────────────────────────────────────

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const COMPRESS_OPTIONS = {
  maxSizeMB:       10,
  maxWidthOrHeight: 2000,
  useWebWorker:    true,
  fileType:        "image/jpeg" as const,
  initialQuality:  0.8,
};

interface UploadStepProps {
  caseId: string;
  onNext: () => void;
}

interface UploadedFile {
  document_id: string;
  name:        string;
  size:        string;
  date:        string;
  ocr_status:  string;
}

function formatBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024).toFixed(0)} KB`;
}

export const UploadStep = ({ caseId, onNext }: UploadStepProps) => {
  const [files,       setFiles]       = useState<UploadedFile[]>([]);
  const [dragging,    setDragging]    = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [qrToken,     setQrToken]     = useState<string | null>(null);
  const [qrLoading,   setQrLoading]   = useState(false);
  const [qrUploadUrl, setQrUploadUrl] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);

  // Dokumente beim Laden der Komponente abrufen
  useEffect(() => {
    loadDocuments();
  }, [caseId]);

  // Polling: neue QR-Uploads + OCR-Status-Updates (alle 2 Sekunden)
  // Läuft solange QR aktiv ODER noch Dokumente in Verarbeitung sind
  useEffect(() => {
    const hasPending = files.some(f => f.ocr_status === "pending" || f.ocr_status === "processing");
    if (qrToken || hasPending) {
      pollRef.current = setInterval(loadDocuments, 2000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [qrToken, files]);

  async function loadDocuments() {
    try {
      const resp: DocumentsResponse = await caseStatusApi.listDocuments(caseId);
      setFiles(
        resp.documents.map(d => ({
          document_id: d.document_id,
          name:        d.filename,
          size:        "–",
          date:        new Date(d.created_at).toLocaleDateString("de-DE"),
          ocr_status:  d.ocr_status,
        }))
      );
    } catch {
      // Fehler beim Laden der Dokumente ignorieren (kein UI-Error nötig)
    }
  }

  async function handleFiles(rawFiles: FileList | null) {
    if (!rawFiles || rawFiles.length === 0) return;
    setError(null);
    setUploading(true);

    for (const raw of Array.from(rawFiles)) {
      try {
        let fileToUpload: File = raw;

        // Bilder clientseitig komprimieren (max 2000px, JPEG, Qualität 80%)
        if (raw.type.startsWith("image/")) {
          fileToUpload = await imageCompression(raw, COMPRESS_OPTIONS);
        }

        if (fileToUpload.size > MAX_FILE_BYTES) {
          setError(`"${raw.name}" ist zu groß (max. 10 MB nach Komprimierung).`);
          continue;
        }

        const resp = await documentsApi.upload(caseId, fileToUpload);
        setFiles(prev => [
          ...prev,
          {
            document_id: resp.document_id,
            name:        resp.filename,
            size:        formatBytes(fileToUpload.size),
            date:        new Date().toLocaleDateString("de-DE"),
            ocr_status:  "pending",
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
      }
    }

    setUploading(false);
  }

  async function handleShowQr() {
    setQrLoading(true);
    setError(null);
    try {
      const resp = await mobileUploadApi.createToken(caseId);
      const base = window.location.origin;
      setQrUploadUrl(`${base}/mobile-upload?token=${resp.token}`);
      setQrToken(resp.token);
    } catch {
      setError("QR-Code konnte nicht generiert werden.");
    } finally {
      setQrLoading(false);
    }
  }

  async function removeFile(doc: UploadedFile) {
    try {
      await documentsApi.delete(caseId, doc.document_id);
      setFiles(prev => prev.filter(f => f.document_id !== doc.document_id));
    } catch {
      setError("Dokument konnte nicht gelöscht werden.");
    }
  }

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 22 }}>1. Upload & Mobile Scan</h3>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* ── Drop zone ── */}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              multiple
              style={{ display: "none" }}
              onChange={e => handleFiles(e.target.files)}
            />
            <div
              onDragOver={e  => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e  => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border:         `2px dashed ${dragging ? colors.orange : colors.border}`,
                borderRadius:   12,
                padding:        "36px 20px",
                display:        "flex",
                flexDirection:  "column",
                alignItems:     "center",
                justifyContent: "center",
                gap:            14,
                background:     dragging ? colors.orangeLight : colors.bg,
                transition:     "all .2s ease",
                cursor:         "pointer",
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
                {uploading ? "Wird hochgeladen…" : "Ziehe PDFs hierher oder klicke zum Hochladen"}
              </p>
              <p style={{ ...textStyles.small, textAlign: "center" }}>
                PDF, JPG, PNG · max. 10 MB
              </p>
              <div style={{ display: "flex", gap: 10 }} onClick={e => e.stopPropagation()}>
                <Button size="sm" onClick={handleShowQr} disabled={qrLoading}>
                  <Icon name="scan" size={13} color="#fff" />
                  {qrLoading ? " Lädt…" : " Mit dem Handy scannen"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  Datei auswählen
                </Button>
              </div>
            </div>

            {/* Fehler-Anzeige */}
            {error && (
              <p style={{
                marginTop: 8,
                fontSize:  12,
                color:     colors.redText,
                fontFamily: typography.sans,
              }}>
                {error}
              </p>
            )}

            {/* QR-Code */}
            {qrToken && qrUploadUrl && (
              <div style={{
                marginTop:    16,
                padding:      16,
                background:   colors.bg,
                border:       `1px solid ${colors.border}`,
                borderRadius: 12,
                textAlign:    "center",
              }}>
                <p style={{ ...textStyles.label, marginBottom: 10 }}>
                  QR-Code mit Handy scannen
                </p>
                <QRCodeSVG value={qrUploadUrl} size={140} />
                <p style={{ ...textStyles.small, marginTop: 8 }}>
                  Gültig 15 Minuten · Automatische Aktualisierung
                </p>
                <button
                  onClick={() => setQrToken(null)}
                  style={{
                    marginTop:  8,
                    background: "none",
                    border:     "none",
                    color:      colors.muted,
                    fontSize:   12,
                    cursor:     "pointer",
                    fontFamily: typography.sans,
                  }}
                >
                  Schließen
                </button>
              </div>
            )}
          </div>

          {/* ── Dateiliste ── */}
          <div>
            <p style={{ ...textStyles.label, marginBottom: 12 }}>
              Hochgeladene Dateien ({files.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {files.length === 0 && (
                <p style={{ ...textStyles.body, fontSize: 13, color: colors.muted }}>
                  Noch keine Dateien hochgeladen.
                </p>
              )}
              {files.map(f => (
                <div
                  key={f.document_id}
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
                    <p style={textStyles.small}>
                      {f.size} · {f.date} ·{" "}
                      <span style={{
                        color: f.ocr_status === "completed" ? colors.greenText
                             : f.ocr_status === "error"     ? colors.redText
                             : colors.muted,
                      }}>
                        {f.ocr_status === "completed" ? "✓ Analysiert"
                       : f.ocr_status === "error"     ? "✗ Fehler"
                       : f.ocr_status === "processing" ? "⏳ Wird analysiert…"
                       : "⏳ Wartend"}
                      </span>
                    </p>
                  </div>

                  <button
                    onClick={() => removeFile(f)}
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 4, borderRadius: 4 }}
                    title="Dokument entfernen"
                  >
                    <Icon name="x" size={14} color={colors.muted} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button onClick={onNext} size="lg" disabled={files.length === 0 || uploading}>
          Weiter zur Analyse <Icon name="arrow" size={15} color="#fff" />
        </Button>
      </div>
    </div>
  );
};
