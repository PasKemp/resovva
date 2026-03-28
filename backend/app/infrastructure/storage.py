"""
StorageService – S3-kompatibler Objektspeicher für Dokumente.

Nutzt boto3 gegen MinIO (lokale Entwicklung) oder AWS S3 (Produktion).
Der Bucket wird beim ersten Zugriff automatisch erstellt falls nicht vorhanden.

Config (.env):
  S3_ENDPOINT    – Intern (Docker): http://minio:9000 | AWS: https://s3.amazonaws.com
  S3_PUBLIC_URL  – Öffentlich erreichbar (Browser): http://localhost:9000
                   Leer lassen → fällt auf S3_ENDPOINT zurück.
                   In Docker Dev: S3_ENDPOINT ist nur intern auflösbar (minio:9000),
                   Presigned-URLs müssen aber localhost:9000 enthalten.
  S3_ACCESS_KEY  – Access Key (MinIO: minioadmin)
  S3_SECRET_KEY  – Secret Key (MinIO: minioadmin)
  S3_BUCKET_NAME – Bucket-Name (z.B. resovva-docs)

Datei-Pfade im Bucket folgen dem Schema: {case_id}/{uuid}.{ext}
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """S3-kompatibler Objektspeicher (MinIO / AWS S3 / Wasabi)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket_name

        # Interner Client: für Up-/Download (läuft im Docker-Netzwerk → minio:9000 OK)
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",  # MinIO ignoriert die Region
        )

        # Presigned-URL-Client: nutzt öffentliche URL (browser-erreichbar).
        # In Docker Dev: s3_endpoint=http://minio:9000 (intern),
        #                s3_public_url=http://localhost:9000 (vom Browser erreichbar)
        # Ohne s3_public_url → selber Client wie oben (AWS S3 / Prod reichen ein Client)
        public_endpoint = settings.s3_public_url or settings.s3_endpoint
        if public_endpoint != settings.s3_endpoint:
            logger.debug(
                "StorageService: Presigned-URL-Client nutzt öffentliche URL: %s", public_endpoint
            )
            self._presigned_client = boto3.client(
                "s3",
                endpoint_url=public_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name="us-east-1",
            )
        else:
            self._presigned_client = self._client

        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Erstellt den Bucket falls er noch nicht existiert (idempotent)."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("S3-Bucket erstellt: %s", self._bucket)
            else:
                raise

    def upload_file(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Lädt Datei-Bytes in den Bucket hoch.

        Args:
            data:         Dateiinhalt als Bytes.
            key:          Pfad im Bucket (z.B. "{case_id}/{uuid}.pdf").
            content_type: MIME-Type der Datei.

        Returns:
            Den S3-Key für spätere Zugriffe.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.debug("Upload: s3://%s/%s (%d Bytes)", self._bucket, key, len(data))
        return key

    def download_file(self, key: str) -> bytes:
        """
        Lädt eine Datei aus dem Bucket herunter.

        Returns:
            Dateiinhalt als Bytes.

        Raises:
            FileNotFoundError: Wenn der Key nicht existiert.
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                raise FileNotFoundError(f"Datei nicht gefunden: {key}") from exc
            raise

    def delete_file(self, key: str) -> None:
        """
        Löscht eine Datei aus dem Bucket (idempotent – kein Fehler falls nicht vorhanden).
        """
        self._client.delete_object(Bucket=self._bucket, Key=key)
        logger.debug("Gelöscht: s3://%s/%s", self._bucket, key)

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generiert eine zeitlich begrenzte Download-URL (z.B. für das Dossier).

        Nutzt den Presigned-URL-Client mit der öffentlich erreichbaren URL
        (S3_PUBLIC_URL), damit der Browser-Redirect funktioniert, auch wenn der
        interne S3_ENDPOINT nur im Docker-Netzwerk auflösbar ist (minio:9000).

        Args:
            key:        S3-Key der Datei.
            expires_in: Gültigkeitsdauer in Sekunden (Standard: 1 Stunde).

        Returns:
            Presigned URL als String (mit browser-erreichbarem Hostnamen).
        """
        return self._presigned_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# ── Lazy Singleton ────────────────────────────────────────────────────────────

_storage: Optional[StorageService] = None


def get_storage() -> StorageService:
    """
    Gibt die globale StorageService-Instanz zurück (Lazy Singleton).
    Erstellt Boto3-Client und prüft/erstellt den Bucket beim ersten Aufruf.
    """
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage
