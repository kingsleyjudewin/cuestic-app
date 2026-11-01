import os
import re
import uuid
import logging
from typing import Optional, BinaryIO
from datetime import timedelta
import firebase_admin
from firebase_admin import credentials, storage
from app.utils.errors import ValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Allowed file extensions for documentation workspace
ALLOWED_EXTENSIONS = {
    "docx", "doc", "pdf", "xlsx", "xls", "pptx", "ppt", "txt", "csv",
    "png", "jpg", "jpeg", "webp"
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or invalid characters."""
    base = os.path.basename(filename).strip()
    clean = re.sub(r"[^\w\.\-\_]", "_", base)
    return clean or "unnamed_document"


class FirebaseStorageService:
    """
    Service for uploading, retrieving, and deleting documents using Firebase Cloud Storage.
    Includes fallback to local storage if Firebase bucket is unprovisioned or offline.
    """

    _bucket = None
    _is_initialized = False

    @classmethod
    def initialize(cls, force_refresh: bool = False) -> bool:
        """Initialize Firebase Storage bucket if credentials exist."""
        if not force_refresh and cls._is_initialized and cls._bucket is not None:
            return True

        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET")

        if cred_path and not os.path.isabs(cred_path):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            cred_path = os.path.join(base_dir, cred_path)

        try:
            # Check if Firebase app is initialized
            try:
                app = firebase_admin.get_app()
            except ValueError:
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    app = firebase_admin.initialize_app(cred)
                else:
                    logger.info("Firebase credentials not configured. Using local document storage.")
                    cls._is_initialized = True
                    return False

            candidate_buckets = []
            if bucket_name:
                candidate_buckets.append(bucket_name.strip())

            # Also infer from project ID if possible
            project_id = getattr(app, "project_id", None)
            if not project_id and cred_path and os.path.exists(cred_path):
                try:
                    import json
                    with open(cred_path, "r") as f:
                        project_id = json.load(f).get("project_id")
                except Exception:
                    pass

            if project_id:
                candidate_buckets.append(f"{project_id}.firebasestorage.app")
                candidate_buckets.append(f"{project_id}.appspot.com")

            cls._bucket = None
            for b_name in candidate_buckets:
                try:
                    b = storage.bucket(name=b_name, app=app)
                    if b.exists():
                        cls._bucket = b
                        logger.info("Firebase Storage connected to bucket: %s", b.name)
                        break
                except Exception as b_err:
                    logger.debug("Bucket candidate '%s' check failed: %s", b_name, b_err)

            if cls._bucket is None:
                # Default bucket check
                try:
                    b = storage.bucket(app=app)
                    if b and b.exists():
                        cls._bucket = b
                        logger.info("Firebase Storage connected to default bucket: %s", b.name)
                except Exception:
                    cls._bucket = None

            if cls._bucket is None:
                logger.info("Firebase Storage bucket not yet enabled on GCP/Firebase. Using local storage fallback.")

            cls._is_initialized = True
            return cls._bucket is not None
        except Exception as e:
            logger.warning("Firebase Storage initialization warning: %s. Using local fallback.", e)
            cls._is_initialized = True
            cls._bucket = None
            return False

    @classmethod
    def get_local_storage_dir(cls) -> str:
        """Directory for local document storage fallback."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "storage"))
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @classmethod
    def upload_file(
        cls,
        file_obj: BinaryIO,
        filename: str,
        team_id: int,
        folder_id: int,
        content_type: Optional[str] = None,
    ) -> dict:
        """
        Upload file stream to storage.
        Returns metadata dict with: storage_path, file_size, content_type, original_filename.
        """
        sanitized = sanitize_filename(filename)
        ext = sanitized.rsplit(".", 1)[-1].lower() if "." in sanitized else ""

        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type '.{ext}' is not permitted for documentation. "
                f"Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                details={"filename": filename}
            )

        # Read content and validate size
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(0)

        if size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                f"File size ({size / (1024 * 1024):.1f} MB) exceeds maximum allowed size (25 MB).",
                details={"file_size": size}
            )

        unique_id = uuid.uuid4().hex[:12]
        storage_rel_path = f"documentation/{team_id}/{folder_id}/{unique_id}_{sanitized}"

        cls.initialize()

        if cls._bucket is not None:
            # Upload to Firebase Cloud Storage
            blob = cls._bucket.blob(storage_rel_path)
            blob.upload_from_file(file_obj, content_type=content_type)
            logger.info("Uploaded to Firebase Storage: %s (%d bytes)", storage_rel_path, size)
            storage_provider = "firebase"
        else:
            if os.environ.get("STRICT_CLOUD_STORAGE", "false").lower() == "true":
                raise ValidationError(
                    "Cloud storage is strictly enforced (STRICT_CLOUD_STORAGE=true), but Firebase Cloud Storage bucket is not reachable. "
                    "Please verify FIREBASE_STORAGE_BUCKET in .env and ensure Cloud Storage is activated in the Firebase Console: "
                    "https://console.firebase.google.com/project/club-management-cuestic/storage",
                    details={"error": "STORAGE_BUCKET_NOT_READY"}
                )
            # Fallback to local persistent storage
            local_target = os.path.join(cls.get_local_storage_dir(), storage_rel_path)
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            with open(local_target, "wb") as f_out:
                file_obj.seek(0)
                f_out.write(file_obj.read())
            logger.info("Saved to local storage fallback: %s (%d bytes)", local_target, size)
            storage_provider = "local"

        return {
            "storage_path": storage_rel_path,
            "original_filename": sanitized,
            "file_size": size,
            "content_type": content_type or "application/octet-stream",
            "storage_provider": storage_provider,
        }

    @classmethod
    def get_file_bytes(cls, storage_path: str) -> bytes:
        """Retrieve file bytes from Firebase Storage or local fallback."""
        cls.initialize()

        if cls._bucket is not None:
            blob = cls._bucket.blob(storage_path)
            if blob.exists():
                return blob.download_as_bytes()

        # Check local storage fallback
        local_target = os.path.join(cls.get_local_storage_dir(), storage_path)
        if os.path.exists(local_target):
            with open(local_target, "rb") as f:
                return f.read()

        raise NotFoundError(f"File at storage path '{storage_path}' was not found.")

    @classmethod
    def generate_download_url(cls, storage_path: str, expires_in_minutes: int = 15) -> Optional[str]:
        """Generate short-lived signed download URL if using Firebase Storage."""
        cls.initialize()
        if cls._bucket is not None:
            try:
                blob = cls._bucket.blob(storage_path)
                if blob.exists():
                    return blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(minutes=expires_in_minutes),
                        method="GET"
                    )
            except Exception as e:
                logger.warning("Could not generate signed URL: %s", e)
        return None

    @classmethod
    def delete_file(cls, storage_path: str) -> bool:
        """Delete file from Firebase Storage or local storage."""
        cls.initialize()
        deleted = False

        if cls._bucket is not None:
            try:
                blob = cls._bucket.blob(storage_path)
                if blob.exists():
                    blob.delete()
                    deleted = True
            except Exception as e:
                logger.warning("Error deleting from Firebase Storage: %s", e)

        local_target = os.path.join(cls.get_local_storage_dir(), storage_path)
        if os.path.exists(local_target):
            try:
                os.remove(local_target)
                deleted = True
            except Exception as e:
                logger.warning("Error deleting local file: %s", e)

        return deleted
