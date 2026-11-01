import os
import uuid
import logging
import time
from typing import Optional, BinaryIO
from datetime import datetime
from app.extensions import db
from app.models.team import Team
from app.models.user import User
from app.models.documentation import EventFolder
from app.models.media import MediaFile
from app.services.firebase_storage_service import FirebaseStorageService, sanitize_filename
from app.services.geotag_service import GeotagService
from app.services.google_drive_service import GoogleDriveService
from app.utils.datetime_utils import utc_now, parse_iso_datetime
from app.utils.errors import ValidationError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

# Category allowed extensions
ALLOWED_EXTENSIONS = {
    MediaFile.CATEGORY_GEOTAGGED: {"jpg", "jpeg", "png", "heic", "heif"},
    MediaFile.CATEGORY_PHOTOS: {"jpg", "jpeg", "png", "webp", "heic", "heif"},
    MediaFile.CATEGORY_VIDEOS: {"mp4", "mov", "m4v", "webm"},
    MediaFile.CATEGORY_POSTERS: {"png", "jpg", "jpeg", "pdf", "ai", "psd", "svg", "webp"},
}

# Max upload size limits in bytes
MAX_SIZES = {
    MediaFile.CATEGORY_GEOTAGGED: 25 * 1024 * 1024,   # 25 MB
    MediaFile.CATEGORY_PHOTOS: 25 * 1024 * 1024,      # 25 MB
    MediaFile.CATEGORY_VIDEOS: 100 * 1024 * 1024,     # 100 MB
    MediaFile.CATEGORY_POSTERS: 50 * 1024 * 1024,     # 50 MB
}


class MediaService:
    """Core domain service for Media Team event folders, media uploads, geotagging, and Google Drive links."""

    _cached_folders_data = None
    _cached_folders_at = 0.0
    _cached_folders_ttl = 1800.0

    @classmethod
    def invalidate_cache(cls):
        """Invalidate in-memory folders cache on write operations."""
        cls._cached_folders_data = None
        cls._cached_folders_at = 0.0

    @classmethod
    def list_folders_data(cls, user: User, search_query: Optional[str] = None) -> list[dict]:
        """Fetch list of folder summaries directly from in-memory cache in sub-millisecond time."""
        cls.verify_access(user, "view event folders")
        now = time.time()
        if not search_query and cls._cached_folders_data is not None and (now - cls._cached_folders_at < cls._cached_folders_ttl):
            return cls._cached_folders_data

        folders = cls.list_folders(user, search_query=search_query)
        data = [f.to_dict(include_documents=False, include_media=False) for f in folders]
        if not search_query:
            cls._cached_folders_data = data
            cls._cached_folders_at = now
        return data

    @staticmethod
    def get_media_team() -> Team:
        """Fetch the unified Media (and Design) team."""
        team = Team.query.filter(
            (Team.id == 3) | (Team.slug == "media") | (Team.name.ilike("media"))
        ).first()
        if not team:
            raise NotFoundError("Media team record not found.")
        return team

    @classmethod
    def verify_access(cls, user: User, action_description: str = "this operation"):
        """Verify that user is an Admin/President or a member of the Media team."""
        if user.is_admin():
            return True

        media_team = cls.get_media_team()
        if user.linked_member and user.linked_member.team_id == media_team.id and user.linked_member.is_active:
            return True

        raise PermissionDeniedError(
            f"You do not have permission to access the Media workspace or perform {action_description}. "
            "Only authorized Media team members and administrators have access."
        )

    # -------------------------------------------------------------------------
    # Event Folder Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_folders(cls, user: User, search_query: Optional[str] = None) -> list[EventFolder]:
        """List event folders associated with the Media team."""
        cls.verify_access(user, "view event folders")
        media_team = cls.get_media_team()

        query = EventFolder.query.filter_by(team_id=media_team.id)
        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            query = query.filter(EventFolder.name.ilike(term))

        return query.order_by(EventFolder.created_at.desc()).all()

    @classmethod
    def create_folder(cls, data: dict, user: User) -> EventFolder:
        """Create a persistent event folder in the database, with optional matching Google Drive folder."""
        cls.verify_access(user, "create an event folder")
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Event name is required.", details={"name": ["Cannot be empty."]})

        media_team = cls.get_media_team()

        # Parse optional event date
        event_date = None
        raw_date = data.get("event_date")
        if raw_date:
            try:
                event_date = parse_iso_datetime(raw_date)
            except Exception:
                try:
                    event_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                except Exception:
                    pass

        description = (data.get("description") or "").strip() or None

        folder = EventFolder(
            name=name,
            description=description,
            event_date=event_date,
            team_id=media_team.id,
            created_by=user.id,
        )

        # Optional matching Google Drive folder creation
        create_in_drive = bool(data.get("create_in_drive", False))
        if create_in_drive:
            try:
                drive_status = GoogleDriveService.get_connection_status(user.id)
                if drive_status.get("is_connected"):
                    drive_folder = GoogleDriveService.create_folder(user.id, name)
                    folder.linked_drive_folder_id = drive_folder.get("id")
                    folder.linked_drive_folder_name = drive_folder.get("name")
                    folder.drive_web_view_link = drive_folder.get("web_view_link")
            except Exception as e:
                logger.warning("Could not create matching Drive folder (retaining DB record): %s", e)

        db.session.add(folder)
        db.session.commit()
        cls.invalidate_cache()
        logger.info("Created Media Event Folder #%d: '%s' by user %s", folder.id, folder.name, user.username)
        return folder

    @classmethod
    def get_folder_by_id(cls, folder_id: int, user: User) -> EventFolder:
        """Get event folder by ID ensuring Media team scope."""
        cls.verify_access(user, "view this event folder")
        media_team = cls.get_media_team()
        folder = EventFolder.query.filter_by(id=folder_id, team_id=media_team.id).first()
        if not folder:
            raise NotFoundError(f"Event folder #{folder_id} not found in the Media workspace.")
        return folder

    @classmethod
    def delete_folder(cls, folder_id: int, user: User) -> bool:
        """Delete event folder and its media files."""
        folder = cls.get_folder_by_id(folder_id, user)

        # Clean up storage objects
        for mf in folder.media_files.all():
            if mf.storage_provider in (MediaFile.PROVIDER_FIREBASE, MediaFile.PROVIDER_LOCAL) and mf.storage_path:
                try:
                    FirebaseStorageService.delete_file(mf.storage_path)
                except Exception as e:
                    logger.warning("Error deleting media file storage: %s", e)

        db.session.delete(folder)
        db.session.commit()
        cls.invalidate_cache()
        return True

    # -------------------------------------------------------------------------
    # Media Uploads & Geotagging
    # -------------------------------------------------------------------------
    @classmethod
    def upload_media(
        cls,
        folder_id: int,
        file_obj: BinaryIO,
        filename: str,
        category: str,
        user: User,
        destination: str = "firebase",
        mime_type: Optional[str] = None
    ) -> MediaFile:
        """
        Upload media file into an event folder (Firebase or Google Drive).
        Inspects EXIF metadata for GPS coordinates, capture time, and camera info.
        """
        folder = cls.get_folder_by_id(folder_id, user)

        if category not in MediaFile.CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. Must be one of: {', '.join(MediaFile.CATEGORIES)}",
                details={"category": list(MediaFile.CATEGORIES)}
            )

        sanitized = sanitize_filename(filename)
        ext = sanitized.rsplit(".", 1)[-1].lower() if "." in sanitized else ""
        allowed = ALLOWED_EXTENSIONS.get(category, set())

        if ext not in allowed:
            raise ValidationError(
                f"File format '.{ext}' is not permitted for category '{category}'. "
                f"Supported formats: {', '.join(sorted(allowed))}",
                details={"filename": filename, "allowed": list(allowed)}
            )

        # Measure file size
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(0)

        max_size = MAX_SIZES.get(category, 25 * 1024 * 1024)
        if size > max_size:
            max_mb = int(max_size / (1024 * 1024))
            raise ValidationError(
                f"File size ({size / (1024 * 1024):.1f} MB) exceeds maximum allowed size ({max_mb} MB) for {category}.",
                details={"file_size": size, "max_size": max_size}
            )

        # Extract Geotagging & EXIF metadata (for image categories)
        exif_meta = {}
        if ext in {"jpg", "jpeg", "png", "heic", "heif", "webp"}:
            exif_meta = GeotagService.extract_image_metadata(file_obj)

        has_gps = bool(exif_meta.get("has_gps"))
        lat = exif_meta.get("latitude")
        lon = exif_meta.get("longitude")
        alt = exif_meta.get("altitude")
        captured_at = exif_meta.get("captured_at")
        cam_make = exif_meta.get("camera_make")
        cam_model = exif_meta.get("camera_model")

        # If user explicitly selected geotagged_photos, verify if GPS was detected
        # (Preserves file either way, labeling GPS accurately)
        if category == MediaFile.CATEGORY_GEOTAGGED and not has_gps:
            logger.info("File '%s' uploaded to Geotagged category has no GPS metadata.", sanitized)

        storage_path = None
        drive_file_id = None
        drive_web_view_link = None
        drive_thumbnail_link = None
        storage_provider = MediaFile.PROVIDER_FIREBASE

        chosen_destination = destination
        drive_target_folder = folder.linked_drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if drive_target_folder:
            drive_target_folder = GoogleDriveService.extract_folder_id(drive_target_folder)

        if chosen_destination == "google_drive" or (
            chosen_destination == "firebase"
            and os.environ.get("DEFAULT_MEDIA_STORAGE", "").lower() == "google_drive"
            and drive_target_folder
        ):
            if not drive_target_folder:
                raise ValidationError(
                    "This event folder is not connected to a Google Drive folder, and no GOOGLE_DRIVE_FOLDER_ID is set in .env. "
                    "Please link a Google Drive folder or configure GOOGLE_DRIVE_FOLDER_ID in .env.",
                    details={"error": "DRIVE_FOLDER_NOT_CONFIGURED"}
                )

            drive_meta = GoogleDriveService.upload_file_to_drive(
                user_id=user.id,
                drive_folder_id=drive_target_folder,
                file_obj=file_obj,
                filename=sanitized,
                mime_type=mime_type
            )
            storage_provider = MediaFile.PROVIDER_GOOGLE_DRIVE
            drive_file_id = drive_meta.get("id")
            drive_web_view_link = drive_meta.get("web_view_link")
            drive_thumbnail_link = drive_meta.get("thumbnail_link")
        else:
            # Firebase Cloud Storage (with local storage fallback)
            unique_id = uuid.uuid4().hex[:12]
            storage_rel_path = f"media/{folder.team_id}/{folder.id}/{category}/{unique_id}_{sanitized}"

            FirebaseStorageService.initialize()
            if FirebaseStorageService._bucket is not None:
                blob = FirebaseStorageService._bucket.blob(storage_rel_path)
                blob.upload_from_file(file_obj, content_type=mime_type or "application/octet-stream")
                storage_provider = MediaFile.PROVIDER_FIREBASE
            else:
                if os.environ.get("STRICT_CLOUD_STORAGE", "false").lower() == "true":
                    raise ValidationError(
                        "Cloud storage is strictly enforced (STRICT_CLOUD_STORAGE=true), but Firebase Cloud Storage bucket is not reachable. "
                        "Please verify FIREBASE_STORAGE_BUCKET in .env and ensure Cloud Storage is activated in the Firebase Console: "
                        "https://console.firebase.google.com/project/club-management-cuestic/storage",
                        details={"error": "STORAGE_BUCKET_NOT_READY"}
                    )
                # Local storage fallback
                local_target = os.path.join(FirebaseStorageService.get_local_storage_dir(), storage_rel_path)
                os.makedirs(os.path.dirname(local_target), exist_ok=True)
                with open(local_target, "wb") as f_out:
                    file_obj.seek(0)
                    f_out.write(file_obj.read())
                storage_provider = MediaFile.PROVIDER_LOCAL

            storage_path = storage_rel_path

        media_file = MediaFile(
            folder_id=folder.id,
            category=category,
            original_filename=sanitized,
            storage_provider=storage_provider,
            storage_path=storage_path,
            drive_file_id=drive_file_id,
            drive_web_view_link=drive_web_view_link,
            drive_thumbnail_link=drive_thumbnail_link,
            mime_type=mime_type or "application/octet-stream",
            file_size=size,
            uploaded_by=user.id,
            has_gps=has_gps,
            gps_latitude=lat,
            gps_longitude=lon,
            gps_altitude=alt,
            captured_at=captured_at,
            camera_make=cam_make,
            camera_model=cam_model,
            status="active",
        )

        db.session.add(media_file)
        db.session.commit()
        logger.info(
            "Media file #%d ('%s') saved in folder #%d [GPS: %s, Provider: %s]",
            media_file.id, media_file.original_filename, folder.id, has_gps, storage_provider
        )
        return media_file

    @classmethod
    def list_folder_media(
        cls,
        folder_id: int,
        user: User,
        category: Optional[str] = None
    ) -> list[MediaFile]:
        """List all active media files in an event folder, optionally filtered by category."""
        folder = cls.get_folder_by_id(folder_id, user)
        q = MediaFile.query.filter_by(folder_id=folder.id, status="active")
        if category and category in MediaFile.CATEGORIES:
            q = q.filter_by(category=category)
        return q.order_by(MediaFile.created_at.desc()).all()

    @classmethod
    def get_media_file(cls, file_id: int, user: User) -> MediaFile:
        """Fetch media file by ID ensuring Media team scope."""
        cls.verify_access(user, "access this media file")
        media_file = db.session.get(MediaFile, file_id)
        if not media_file or media_file.status != "active":
            raise NotFoundError(f"Media file #{file_id} not found.")

        # Ensure folder belongs to media team
        media_team = cls.get_media_team()
        if media_file.folder.team_id != media_team.id:
            raise PermissionDeniedError("File belongs to a different team.")

        return media_file

    @classmethod
    def delete_media_file(cls, file_id: int, user: User) -> bool:
        """
        Delete or unlink a media file.
        For Firebase/local: removes object from storage.
        For Google Drive: unlinks the database record without deleting the original file in Drive.
        """
        media_file = cls.get_media_file(file_id, user)

        if media_file.storage_provider in (MediaFile.PROVIDER_FIREBASE, MediaFile.PROVIDER_LOCAL) and media_file.storage_path:
            try:
                FirebaseStorageService.delete_file(media_file.storage_path)
            except Exception as e:
                logger.warning("Notice deleting storage object: %s", e)

        db.session.delete(media_file)
        db.session.commit()
        return True

    # -------------------------------------------------------------------------
    # Google Drive Linking & Management
    # -------------------------------------------------------------------------
    @classmethod
    def link_drive_folder(
        cls,
        folder_id: int,
        drive_folder_id: str,
        drive_folder_name: str,
        web_view_link: Optional[str],
        user: User
    ) -> EventFolder:
        """Link an existing Google Drive folder to an event folder."""
        folder = cls.get_folder_by_id(folder_id, user)
        if not drive_folder_id:
            raise ValidationError("Google Drive folder ID is required.")

        extracted_id = GoogleDriveService.extract_folder_id(drive_folder_id)
        folder.linked_drive_folder_id = extracted_id
        folder.linked_drive_folder_name = (drive_folder_name or "Google Drive Folder").strip()
        folder.drive_web_view_link = web_view_link or f"https://drive.google.com/drive/folders/{extracted_id}"
        folder.updated_at = utc_now()

        db.session.commit()
        logger.info("Linked Drive folder '%s' (%s) to Event Folder #%d", drive_folder_name, drive_folder_id, folder.id)
        return folder

    @classmethod
    def unlink_drive_folder(cls, folder_id: int, user: User) -> EventFolder:
        """Unlink Google Drive folder from event folder without deleting Drive files."""
        folder = cls.get_folder_by_id(folder_id, user)
        folder.linked_drive_folder_id = None
        folder.linked_drive_folder_name = None
        folder.drive_web_view_link = None
        folder.updated_at = utc_now()

        db.session.commit()
        return folder

    @classmethod
    def link_drive_file(
        cls,
        folder_id: int,
        drive_file_id: str,
        user: User,
        category: Optional[str] = None
    ) -> MediaFile:
        """
        Link an existing Google Drive file into an event folder.
        Avoids downloading or duplicating bytes into Firebase.
        """
        folder = cls.get_folder_by_id(folder_id, user)

        # Check if already linked
        existing = MediaFile.query.filter_by(
            folder_id=folder.id,
            drive_file_id=drive_file_id,
            status="active"
        ).first()
        if existing:
            return existing

        # Fetch metadata from Drive API
        meta = GoogleDriveService.get_file_metadata(user.id, drive_file_id)
        mime = meta.get("mime_type", "")
        chosen_cat = category

        if not chosen_cat or chosen_cat not in MediaFile.CATEGORIES:
            if mime.startswith("image/"):
                chosen_cat = MediaFile.CATEGORY_PHOTOS
            elif mime.startswith("video/"):
                chosen_cat = MediaFile.CATEGORY_VIDEOS
            else:
                chosen_cat = MediaFile.CATEGORY_POSTERS

        media_file = MediaFile(
            folder_id=folder.id,
            category=chosen_cat,
            original_filename=meta.get("name") or "Drive File",
            storage_provider=MediaFile.PROVIDER_GOOGLE_DRIVE,
            drive_file_id=meta.get("id"),
            drive_web_view_link=meta.get("web_view_link"),
            drive_thumbnail_link=meta.get("thumbnail_link"),
            mime_type=mime,
            file_size=meta.get("file_size"),
            uploaded_by=user.id,
            has_gps=False,
            status="active",
        )

        db.session.add(media_file)
        db.session.commit()
        return media_file
