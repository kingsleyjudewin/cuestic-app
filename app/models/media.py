from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class MediaFile(db.Model):
    """File metadata stored in an event folder for the Media Team."""
    __tablename__ = "media_files"

    CATEGORY_GEOTAGGED = "geotagged_photos"
    CATEGORY_PHOTOS = "photos"
    CATEGORY_VIDEOS = "videos"
    CATEGORY_POSTERS = "posters"

    CATEGORIES = [
        CATEGORY_GEOTAGGED,
        CATEGORY_PHOTOS,
        CATEGORY_VIDEOS,
        CATEGORY_POSTERS,
    ]

    PROVIDER_FIREBASE = "firebase"
    PROVIDER_GOOGLE_DRIVE = "google_drive"
    PROVIDER_LOCAL = "local"

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(
        db.Integer,
        db.ForeignKey("event_folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category = db.Column(db.String(50), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_provider = db.Column(db.String(50), nullable=False, default=PROVIDER_FIREBASE)
    storage_path = db.Column(db.String(500), nullable=True, index=True)
    drive_file_id = db.Column(db.String(255), nullable=True, index=True)
    drive_web_view_link = db.Column(db.String(500), nullable=True)
    drive_thumbnail_link = db.Column(db.String(500), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # in bytes
    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    has_gps = db.Column(db.Boolean, default=False, nullable=False)
    gps_latitude = db.Column(db.Float, nullable=True)
    gps_longitude = db.Column(db.Float, nullable=True)
    gps_altitude = db.Column(db.Float, nullable=True)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    camera_make = db.Column(db.String(100), nullable=True)
    camera_model = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default="active", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    folder = db.relationship("EventFolder", back_populates="media_files")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])

    def format_file_size(self) -> str:
        """Format bytes to human-readable size string."""
        if not self.file_size:
            return "0 B"
        bytes_val = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}" if unit != "B" else f"{int(bytes_val)} B"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} TB"

    @property
    def maps_url(self) -> str | None:
        """Generate Google Maps URL if GPS coordinates exist."""
        if self.has_gps and self.gps_latitude is not None and self.gps_longitude is not None:
            return f"https://maps.google.com/?q={self.gps_latitude},{self.gps_longitude}"
        return None

    def to_dict(self) -> dict:
        """Serialize media file to dictionary."""
        uploader_name = self.uploader.username if self.uploader else None
        return {
            "id": self.id,
            "folder_id": self.folder_id,
            "category": self.category,
            "original_filename": self.original_filename,
            "storage_provider": self.storage_provider,
            "storage_path": self.storage_path,
            "drive_file_id": self.drive_file_id,
            "drive_web_view_link": self.drive_web_view_link,
            "drive_thumbnail_link": self.drive_thumbnail_link,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "file_size_formatted": self.format_file_size(),
            "uploaded_by": self.uploaded_by,
            "uploader_name": uploader_name,
            "has_gps": self.has_gps,
            "gps_latitude": self.gps_latitude,
            "gps_longitude": self.gps_longitude,
            "gps_altitude": self.gps_altitude,
            "captured_at": format_iso_utc(self.captured_at) if self.captured_at else None,
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
            "maps_url": self.maps_url,
            "status": self.status,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class GoogleDriveIntegration(db.Model):
    """Google Drive OAuth 2.0 credentials and connection metadata for a user."""
    __tablename__ = "google_drive_integrations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    team_id = db.Column(
        db.Integer,
        db.ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True
    )
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expiry = db.Column(db.DateTime(timezone=True), nullable=True)
    scope = db.Column(db.String(255), nullable=True)
    google_email = db.Column(db.String(255), nullable=True)
    google_user_id = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationship
    user = db.relationship("User")

    def to_dict(self) -> dict:
        """Serialize integration without exposing confidential tokens."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "google_email": self.google_email,
            "is_active": self.is_active,
            "token_expiry": format_iso_utc(self.token_expiry) if self.token_expiry else None,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
