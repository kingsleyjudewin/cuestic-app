"""Central persistent file storage: Firebase Cloud Storage with a local-directory backend.

Backend selection
-----------------
* Firebase Storage is used whenever a service-account JSON and a reachable bucket exist.
  Credentials are read from (first match wins):
    FIREBASE_CREDENTIALS_PATH, GOOGLE_APPLICATION_CREDENTIALS,
    /etc/secrets/firebase-service-account.json (Render Secret File default).
* Otherwise files are written under STORAGE_LOCAL_ROOT (default: instance/storage). In
  production that directory must be a persistent disk (e.g. a Render Disk at /var/data);
  Render's normal filesystem is wiped on every deploy/restart.

Strict mode (STRICT_CLOUD_STORAGE)
----------------------------------
When strict, an upload fails loudly instead of silently landing on an ephemeral disk.
Default: strict in production unless STORAGE_LOCAL_ROOT is explicitly configured.

Object keys are relative ("documentation/<team>/<folder>/<uuid>_<name>") and identical in both
backends, so files can be migrated between them without database changes
(see scripts/migrate_to_firebase_storage.py).
"""
import os
import re
import time
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

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LEGACY_LOCAL_DIR = os.path.join(_BASE_DIR, "instance", "storage")
_RENDER_SECRET_DEFAULT = "/etc/secrets/firebase-service-account.json"
_INIT_RETRY_SECONDS = 60


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or invalid characters."""
    base = os.path.basename(filename or "").strip()
    clean = re.sub(r"[^\w\.\-\_]", "_", base)
    clean = clean.lstrip(".")  # no hidden files / ".." names
    return clean or "unnamed_document"


def _env_flag(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _resolve_credentials_path() -> Optional[str]:
    for candidate in (
        os.environ.get("FIREBASE_CREDENTIALS_PATH"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        _RENDER_SECRET_DEFAULT,
    ):
        if not candidate:
            continue
        path = candidate if os.path.isabs(candidate) else os.path.join(_BASE_DIR, candidate)
        if os.path.isfile(path):
            return path
    return None


class StorageUnavailableError(ValidationError):
    """Raised when persistent storage is required but not reachable (HTTP 503)."""
    status_code = 503
    code = "STORAGE_UNAVAILABLE"


class FirebaseStorageService:
    """
    Service for uploading, retrieving, and deleting files using Firebase Cloud Storage,
    with a configurable local-directory backend (see module docstring).
    """

    _bucket = None
    _is_initialized = False
    _last_init_attempt = 0.0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @classmethod
    def is_strict(cls) -> bool:
        explicit = _env_flag("STRICT_CLOUD_STORAGE")
        if explicit is not None:
            return explicit
        is_production = os.environ.get("FLASK_ENV", "").lower() == "production"
        return is_production and not os.environ.get("STORAGE_LOCAL_ROOT")

    @classmethod
    def initialize(cls, force_refresh: bool = False) -> bool:
        """Initialize Firebase Storage bucket if credentials exist."""
        if not force_refresh and cls._is_initialized:
            if cls._bucket is not None:
                return True
            # Retry periodically so a transient failure at boot does not pin us to local disk.
            if time.time() - cls._last_init_attempt < _INIT_RETRY_SECONDS:
                return False
        cls._last_init_attempt = time.time()

        cred_path = _resolve_credentials_path()
        bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET")

        try:
            # Check if Firebase app is initialized
            try:
                app = firebase_admin.get_app()
            except ValueError:
                if cred_path:
                    cred = credentials.Certificate(cred_path)
                    options = {"storageBucket": bucket_name.strip()} if bucket_name else None
                    app = firebase_admin.initialize_app(cred, options)
                else:
                    logger.info("Firebase credentials not configured. Using local document storage.")
                    cls._is_initialized = True
                    return False

            candidate_buckets = []
            if bucket_name:
                candidate_buckets.append(bucket_name.strip())

            # Also infer from project ID if possible
            project_id = getattr(app, "project_id", None)
            if not project_id and cred_path:
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
                logger.warning(
                    "Firebase Storage bucket is not reachable (is Cloud Storage enabled for this project?). "
                    "Falling back to local storage at %s%s.",
                    cls.get_local_storage_dir(),
                    " — uploads will be REJECTED because strict cloud storage is on" if cls.is_strict() else "",
                )

            cls._is_initialized = True
            return cls._bucket is not None
        except Exception as e:
            logger.warning("Firebase Storage initialization warning: %s. Using local fallback.", type(e).__name__)
            cls._is_initialized = True
            cls._bucket = None
            return False

    @classmethod
    def backend_name(cls) -> str:
        return "firebase" if cls.initialize() else "local"

    @classmethod
    def get_local_storage_dir(cls) -> str:
        """Directory for the local storage backend (STORAGE_LOCAL_ROOT, default instance/storage)."""
        base_dir = os.path.abspath(os.environ.get("STORAGE_LOCAL_ROOT") or _LEGACY_LOCAL_DIR)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @classmethod
    def _local_roots(cls) -> list:
        roots = [cls.get_local_storage_dir()]
        if os.path.isdir(_LEGACY_LOCAL_DIR) and os.path.realpath(_LEGACY_LOCAL_DIR) != os.path.realpath(roots[0]):
            roots.append(_LEGACY_LOCAL_DIR)  # read-only compatibility for files saved before migration
        return roots

    @staticmethod
    def _validate_key(storage_path: str) -> str:
        """Reject absolute paths, '..' segments and NUL bytes in object keys."""
        key = (storage_path or "").replace("\\", "/").strip()
        if not key or key.startswith("/") or "\x00" in key or any(part == ".." for part in key.split("/")):
            raise NotFoundError("File was not found.")
        return key

    @classmethod
    def _safe_local_path(cls, storage_path: str, root: Optional[str] = None) -> str:
        key = cls._validate_key(storage_path)
        root_real = os.path.realpath(root or cls.get_local_storage_dir())
        target = os.path.realpath(os.path.join(root_real, key))
        if not target.startswith(root_real + os.sep):
            raise NotFoundError("File was not found.")
        return target

    # ------------------------------------------------------------------
    # Generic object operations
    # ------------------------------------------------------------------
    @classmethod
    def put_object(cls, storage_rel_path: str, file_obj: BinaryIO, content_type: Optional[str] = None) -> str:
        """Store a stream under storage_rel_path. Returns the provider used ("firebase" or "local")."""
        key = cls._validate_key(storage_rel_path)
        cls.initialize()
        file_obj.seek(0)

        if cls._bucket is not None:
            blob = cls._bucket.blob(key)
            blob.upload_from_file(file_obj, content_type=content_type or "application/octet-stream")
            return "firebase"

        if cls.is_strict():
            raise StorageUnavailableError(
                "Persistent file storage is not available right now, so the file was not saved. "
                "Ask an administrator to enable Firebase Cloud Storage (or a persistent disk) on the server.",
                details={"error": "STORAGE_BUCKET_NOT_READY"},
            )

        local_target = cls._safe_local_path(key)
        os.makedirs(os.path.dirname(local_target), exist_ok=True)
        tmp_target = f"{local_target}.part-{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp_target, "wb") as f_out:
                while True:
                    chunk = file_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    f_out.write(chunk)
            os.replace(tmp_target, local_target)  # atomic: no half-written files on interruption
        finally:
            if os.path.exists(tmp_target):
                os.remove(tmp_target)
        return "local"

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

        storage_provider = cls.put_object(storage_rel_path, file_obj, content_type)
        logger.info("Stored document %s (%d bytes) via %s storage", storage_rel_path, size, storage_provider)

        return {
            "storage_path": storage_rel_path,
            "original_filename": sanitized,
            "file_size": size,
            "content_type": content_type or "application/octet-stream",
            "storage_provider": storage_provider,
        }

    @classmethod
    def get_file_bytes(cls, storage_path: str) -> bytes:
        """Retrieve file bytes from Firebase Storage or the local backend."""
        key = cls._validate_key(storage_path)
        cls.initialize()

        if cls._bucket is not None:
            blob = cls._bucket.blob(key)
            if blob.exists():
                return blob.download_as_bytes()

        for root in cls._local_roots():
            local_target = cls._safe_local_path(key, root)
            if os.path.isfile(local_target):
                with open(local_target, "rb") as f:
                    return f.read()

        raise NotFoundError("The requested file was not found in storage.")

    @classmethod
    def generate_download_url(cls, storage_path: str, expires_in_minutes: int = 15) -> Optional[str]:
        """Generate short-lived signed download URL if using Firebase Storage."""
        cls.initialize()
        if cls._bucket is not None:
            try:
                blob = cls._bucket.blob(cls._validate_key(storage_path))
                if blob.exists():
                    return blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(minutes=expires_in_minutes),
                        method="GET"
                    )
            except Exception as e:
                logger.warning("Could not generate signed URL: %s", type(e).__name__)
        return None

    @classmethod
    def delete_file(cls, storage_path: str) -> bool:
        """Delete file from Firebase Storage and/or local storage."""
        try:
            key = cls._validate_key(storage_path)
        except NotFoundError:
            return False
        cls.initialize()
        deleted = False

        if cls._bucket is not None:
            try:
                blob = cls._bucket.blob(key)
                if blob.exists():
                    blob.delete()
                    deleted = True
            except Exception as e:
                logger.warning("Error deleting from Firebase Storage: %s", type(e).__name__)

        for root in cls._local_roots():
            local_target = cls._safe_local_path(key, root)
            if os.path.isfile(local_target):
                try:
                    os.remove(local_target)
                    deleted = True
                except Exception as e:
                    logger.warning("Error deleting local file: %s", type(e).__name__)

        return deleted
