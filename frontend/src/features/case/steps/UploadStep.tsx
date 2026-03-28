import { useCallback, useEffect, useRef, useState } from "react";
import imageCompression from "browser-image-compression";
import { QRCodeSVG } from "qrcode.react";
import { colors, textStyles, typography } from "../../../theme/tokens";
import { Button, Card, Icon } from "../../../components";
import { documentsApi, mobileUploadApi } from "../../../services/api";
import type { DocumentListItem } from "../../../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 — Upload & Mobile Scan
// ─────────────────────────────────────────────────────────────────────────────

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const COMPRESS_OPTIONS = {
  maxSizeMB:        10,
  maxWidthOrHeight: 2000,
  useWebWorker:     true,
  fileType:         "image/jpeg" as const,
  initialQuality:   0.8,
};

interface UploadStepProps {
  caseId:            string;
  /** Dokumentenliste vom Parent (CaseFlow pollt zentral). */
  docs:              DocumentListItem[];
  onNext:            () => void;
  onCanNextChange?:  (can: boolean) => void;
  /** Vor dem Upload aufrufen. Gibt false zurück → Upload abbrechen. */
  onBeforeUpload?:   () => Promise<boolean>;
  /** Empfohlene Dokumente aus dem Fall-Steckbrief (US-7.3). */
  recommendedDocs?:  string[];
}

interface UploadedFile {
  document_id: string;
  name:        string;
  size:        string;
  date:        string;
  ocr_status:  string;
}


const FileRow: React.FC<{ file: UploadedFile; onRemove: (f: UploadedFile) => void }> = ({ file: f, onRemove }) => {
  const [hovered, setHovered] = useState(false);
  const done = f.ocr_status === "completed";
  const err  = f.ocr_status === "error";

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:   hovered ? colors.bg : colors.white,
        border:       `1px solid ${colors.border}`,
        borderRadius: 8,
        padding:      "10px 12px",
        display:      "flex",
        alignItems:   "center",
        gap:          10,
        transition:   "background .15s",
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
          fontSize: 12, fontWeight: 600, color: colors.dark, fontFamily: typography.sans,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {f.name}
        </p>
        <p style={textStyles.small}>
          {f.size} · {f.date} ·{" "}
          <span style={{ color: done ? "#27AE60" : err ? colors.redText : colors.orange }}>
            {done ? "✓ Analysiert" : err ? "✗ Fehler" : "⏳ Wird verarbeitet…"}
          </span>
        </p>
      </div>

      <button
        onClick={() => onRemove(f)}
        style={{
          background: "none", border: "none", cursor: "pointer",
          padding: 4, borderRadius: 4,
          opacity: hovered ? 1 : 0, transition: "opacity .15s",
        }}
        title="Dokument entfernen"
      >
        <Icon name="x" size={14} color={colors.muted} />
      </button>
    </div>
  );
};

/**
 * Step 1: Dokument-Upload per Drag-Drop, Dateiauswahl oder QR-Code (Handy).
 * Dokumentenliste wird zentral von CaseFlow gepflegt und als `docs` übergeben.
 */
export const UploadStep: React.FC<UploadStepProps> = ({ caseId, docs, onNext: _onNext, onCanNextChange, onBeforeUpload, recommendedDocs = [] }) => {
  const [localFiles,   setLocalFiles]   = useState<UploadedFile[]>([]);
  const [dragging,     setDragging]     = useState(false);
  const [uploading,    setUploading]    = useState(false);
  const [error,        setError]        = useState<string | null>(null);
  const [qrToken,      setQrToken]      = useState<string | null>(null);
  const [qrLoading,    setQrLoading]    = useState(false);
  const [qrUploadUrl,  setQrUploadUrl]  = useState<string | null>(null);

  const [activeTab,    setActiveTab]    = useState<"file" | "text">("file");
  const [textTitle,    setTextTitle]    = useState("");
  const [textContent,  setTextContent]  = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Dokumentenliste aus Parent-Props ableiten (CaseFlow pollt zentral)
  useEffect(() => {
    setLocalFiles(
      docs.map(d => ({
        document_id: d.document_id,
        name:        d.filename,
        size:        "–",
        date:        new Date(d.created_at).toLocaleDateString("de-DE"),
        ocr_status:  d.ocr_status,
      }))
    );
  }, [docs]);

  // Eltern-Komponente über Datei-Verfügbarkeit informieren
  useEffect(() => {
    onCanNextChange?.(docs.length > 0);
  }, [docs.length, onCanNextChange]);

  const handleFiles = useCallback(async (rawFiles: FileList | null) => {
    if (!rawFiles || rawFiles.length === 0) return;
    // FileList vor dem ersten await in ein Array kopieren: die FileList ist ein
    // live-Objekt — e.target.value = "" (synchron nach handleFiles-Aufruf) leert
    // sie, bevor der await-Resumption-Punkt erreicht wird.
    const files = Array.from(rawFiles);
    // Guard: bei bereits gestarteter Analyse Dialog anzeigen
    if (onBeforeUpload) {
      const proceed = await onBeforeUpload();
      if (!proceed) return;
    }
    setError(null);
    setUploading(true);

    for (const raw of files) {
      try {
        let fileToUpload: File = raw;

        // Bilder clientseitig komprimieren (max 2000px, JPEG, Qualität 80%)
        // Originalname explizit erhalten, da imageCompression manchmal ein
        // namenloses Blob zurückgibt → "blob" als Dateiname im Backend
        if (raw.type.startsWith("image/")) {
          const compressed = await imageCompression(raw, COMPRESS_OPTIONS);
          fileToUpload = new File([compressed], raw.name, { type: compressed.type });
        }

        if (fileToUpload.size > MAX_FILE_BYTES) {
          setError(`"${raw.name}" ist zu groß (max. 10 MB nach Komprimierung).`);
          continue;
        }

        await documentsApi.upload(caseId, fileToUpload);
        // Kein lokales State-Update nötig: CaseFlow-Polling aktualisiert `docs`
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
      }
    }

    setUploading(false);
  }, [caseId, onBeforeUpload]);

  const handleTextUpload = useCallback(async () => {
    if (!textContent.trim()) return;
    const finalFileName = textTitle.trim() ? `${textTitle.trim()}.txt` : `E-Mail_Text_${Date.now()}.txt`;
    const textFile = new File([textContent], finalFileName, { type: "text/plain" });

    const dt = new DataTransfer();
    dt.items.add(textFile);
    await handleFiles(dt.files);

    setTextContent("");
    setTextTitle("");
    setActiveTab("file");
  }, [textContent, textTitle, handleFiles]);

  const handleShowQr = useCallback(async () => {
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
  }, [caseId]);

  const removeFile = useCallback(async (doc: UploadedFile) => {
    try {
      await documentsApi.delete(caseId, doc.document_id);
      // CaseFlow-Polling entfernt das Dokument automatisch aus `docs`
    } catch {
      setError("Dokument konnte nicht gelöscht werden.");
    }
  }, [caseId]);

  return (
    <div className="fade-in">
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ ...textStyles.h3, marginBottom: 20 }}>1. Upload & Mobile Scan</h3>

        {/* ── Empfohlene Dokumente (US-7.3) ── */}
        {recommendedDocs.length > 0 && (
          <div style={{
            background:   colors.tealLight,
            border:       `1px solid ${colors.teal}`,
            borderRadius: 10,
            padding:      "14px 16px",
            marginBottom: 20,
          }}>
            <p style={{ ...textStyles.label, color: colors.teal, marginBottom: 8 }}>
              Das brauchst du für diesen Fall
            </p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {recommendedDocs.map((doc, i) => (
                <li key={i} style={{ ...textStyles.body, fontSize: 13, marginBottom: 4, color: colors.dark }}>
                  {doc}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ── Tabs ── */}
        <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
          <button
            onClick={() => setActiveTab("file")}
            style={{
              flex: 1, padding: "10px 0",
              background: activeTab === "file" ? colors.orangeLight : "transparent",
              border: `1.5px solid ${activeTab === "file" ? colors.orange : colors.border}`,
              borderRadius: 8, color: activeTab === "file" ? colors.orange : colors.mid,
              fontWeight: 600, fontFamily: typography.sans, fontSize: 13, cursor: "pointer",
            }}
          >
            📄 Dokument hochladen
          </button>
          <button
            onClick={() => setActiveTab("text")}
            style={{
              flex: 1, padding: "10px 0",
              background: activeTab === "text" ? colors.orangeLight : "transparent",
              border: `1.5px solid ${activeTab === "text" ? colors.orange : colors.border}`,
              borderRadius: 8, color: activeTab === "text" ? colors.orange : colors.mid,
              fontWeight: 600, fontFamily: typography.sans, fontSize: 13, cursor: "pointer",
            }}
          >
            ✉️ E-Mail / Text einfügen
          </button>
        </div>

        {activeTab === "file" ? (
          <>
            {/* ── Drop zone ── */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              multiple
              style={{ display: "none" }}
              onChange={e => {
                handleFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <div
              onDragOver={e  => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e  => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border:         `2px dashed ${dragging ? colors.orange : colors.orange + "60"}`,
                borderRadius:   14,
                minHeight:      200,
                padding:        "32px 24px",
                display:        "flex",
                flexDirection:  "column",
                alignItems:     "center",
                justifyContent: "center",
                gap:            14,
                background:     dragging ? colors.orangeLight : "#FFF8F5",
                transition:     "all .2s ease",
                cursor:         "pointer",
                marginBottom:   20,
              }}
            >
              <div style={{
                width: 56, height: 56,
                background:   colors.orangeLight,
                borderRadius: 14,
                display:      "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Icon name="upload" size={26} color={colors.orange} />
              </div>
              <p style={{ ...textStyles.body, fontSize: 13, textAlign: "center", color: colors.mid }}>
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
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 20 }}>
            <input
              type="text"
              placeholder="Titel, z.B. E-Mail vom 12.05."
              value={textTitle}
              onChange={e => setTextTitle(e.target.value)}
              style={{
                width: "100%", padding: "12px 14px", fontFamily: typography.sans, fontSize: 13,
                border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
                background: colors.bg, color: colors.dark, boxSizing: "border-box",
              }}
            />
            <textarea
              placeholder="Kopiere den Text deiner E-Mail hier hinein..."
              value={textContent}
              onChange={e => setTextContent(e.target.value)}
              rows={8}
              style={{
                width: "100%", padding: "12px 14px", fontFamily: typography.sans, fontSize: 13,
                border: `1.5px solid ${colors.border}`, borderRadius: 8, outline: "none",
                background: colors.bg, color: colors.dark, resize: "vertical", boxSizing: "border-box",
                minHeight: 180,
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
              <Button
                disabled={!textContent.trim() || uploading}
                onClick={handleTextUpload}
              >
                {uploading ? "Wird hochgeladen…" : "Text als Dokument hinzufügen"}
              </Button>
            </div>
          </div>
        )}

        {/* Fehler-Anzeige */}
        {error && (
          <p style={{ marginBottom: 12, fontSize: 12, color: colors.redText, fontFamily: typography.sans }}>
            {error}
          </p>
        )}

        {/* QR-Code */}
        {qrToken && qrUploadUrl && (
          <div style={{
            marginBottom: 20,
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
                marginTop: 8, background: "none", border: "none",
                color: colors.muted, fontSize: 12, cursor: "pointer", fontFamily: typography.sans,
              }}
            >
              Schließen
            </button>
          </div>
        )}

        {/* ── Dateiliste ── */}
        {localFiles.length > 0 && (
          <>
            <p style={{ ...textStyles.label, marginBottom: 12 }}>
              Hochgeladene Dateien ({localFiles.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {localFiles.map(f => (
                <FileRow key={f.document_id} file={f} onRemove={removeFile} />
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
};
