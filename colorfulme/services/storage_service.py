from __future__ import annotations

import os
from pathlib import Path
import uuid

from flask import current_app, url_for


class StorageService:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET', '').strip()
        self.region = os.getenv('S3_REGION', '').strip() or 'us-east-1'
        self.access_key = os.getenv('S3_ACCESS_KEY', '').strip()
        self.secret_key = os.getenv('S3_SECRET_KEY', '').strip()
        self.endpoint_url = os.getenv('S3_ENDPOINT_URL', '').strip() or None

        self._s3_client = None
        if self.bucket and self.access_key and self.secret_key:
            try:
                import boto3

                self._s3_client = boto3.client(
                    's3',
                    region_name=self.region,
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                )
            except Exception:
                self._s3_client = None

        self.local_root = Path(current_app.instance_path) / 'generated'
        self.local_root.mkdir(parents=True, exist_ok=True)

    @property
    def uses_s3(self) -> bool:
        return self._s3_client is not None

    def save_bytes(self, payload: bytes, *, extension: str, folder: str = 'assets') -> tuple[str, str]:
        safe_ext = extension.lstrip('.').lower()
        key = f"{folder.strip('/')}/{uuid.uuid4().hex}.{safe_ext}"

        if self.uses_s3:
            self._s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=payload,
                ContentType=self._mime_for_ext(safe_ext),
            )
            return key, self.get_download_url(key)

        path = self.local_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return key, self.get_download_url(key)

    def get_download_url(self, key: str, expires_seconds: int = 3600) -> str:
        if self.uses_s3:
            return self._s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_seconds,
            )

        return url_for('web.local_asset', key=key, _external=True)

    def absolute_local_path(self, key: str) -> Path:
        return self.local_root / key

    @staticmethod
    def _mime_for_ext(ext: str) -> str:
        if ext == 'png':
            return 'image/png'
        if ext == 'pdf':
            return 'application/pdf'
        return 'application/octet-stream'
