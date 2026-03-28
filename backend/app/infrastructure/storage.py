"""
Storage service for S3-compatible object storage.

Handles file uploads, downloads, deletions, and generation of presigned URLs
using boto3. Supports both internal Docker networking and public browser access.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    S3-compatible object storage service (MinIO / AWS S3).

    Handles bucket lifecycle and file operations. Uses two clients if
    S3_PUBLIC_URL is configured to ensure presigned URLs are browser-reachable.
    """

    def __init__(self) -> None:
        """
        Initialize S3 clients and ensure the target bucket exists.
        """
        settings = get_settings()
        self._bucket = settings.s3_bucket_name

        # Internal client for server-side operations (e.g., within Docker)
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
        )

        # Public client for presigned URLs (must be browser-reachable)
        public_endpoint = settings.s3_public_url or settings.s3_endpoint
        if public_endpoint != settings.s3_endpoint:
            logger.debug(
                "StorageService: using public endpoint for presigned URLs",
                extra={"endpoint": public_endpoint}
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
        """
        Create the bucket if it does not exist (idempotent).

        Raises:
            ClientError: If bucket head/create fails unexpectedly.
        """
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("S3 bucket created", extra={"bucket": self._bucket})
            else:
                raise

    def upload_file(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file bytes to the bucket.

        Args:
            data: File content as bytes.
            key: Path within the bucket.
            content_type: MIME type of the file.

        Returns:
            str: The S3 key of the uploaded file.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.debug(
            "File uploaded",
            extra={"bucket": self._bucket, "key": key, "size": len(data)}
        )
        return key

    def download_file(self, key: str) -> bytes:
        """
        Download a file from the bucket.

        Args:
            key: Path within the bucket.

        Returns:
            bytes: File content.

        Raises:
            FileNotFoundError: If the key does not exist.
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                raise FileNotFoundError(f"File not found in S3: {key}") from exc
            raise

    def delete_file(self, key: str) -> None:
        """
        Delete a file from the bucket (idempotent).

        Args:
            key: Path within the bucket.
        """
        self._client.delete_object(Bucket=self._bucket, Key=key)
        logger.debug("File deleted", extra={"bucket": self._bucket, "key": key})

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a time-limited download URL.

        Uses the presigned client (configured with public endpoint) to ensure
        the URL is accessible by the user's browser.

        Args:
            key: S3 key of the file.
            expires_in: Expiry duration in seconds (default: 1 hour).

        Returns:
            str: The presigned URL.
        """
        return self._presigned_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage() -> StorageService:
    """
    Get the global StorageService instance (Lazy Singleton).

    Returns:
        StorageService: The initialized storage service.
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
