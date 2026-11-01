import json
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class EventFolder(db.Model):
    """Event folder storing event-related documents and reports for a team."""
    __tablename__ = "event_folders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.DateTime(timezone=True), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_drive_folder_id = db.Column(db.String(255), nullable=True)
    linked_drive_folder_name = db.Column(db.String(255), nullable=True)
    drive_web_view_link = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    team = db.relationship("Team")
    creator = db.relationship("User", foreign_keys=[created_by])
    documents = db.relationship(
        "FolderDocument",
        back_populates="folder",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="desc(FolderDocument.created_at)"
    )
    reports = db.relationship(
        "ActivityReport",
        back_populates="folder",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="desc(ActivityReport.created_at)"
    )
    media_files = db.relationship(
        "MediaFile",
        back_populates="folder",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="desc(MediaFile.created_at)"
    )

    def to_dict(self, include_documents: bool = False, include_media: bool = False) -> dict:
        """Serialize event folder to dictionary."""
        media_list = self.media_files.all() if hasattr(self, "media_files") else []
        geotagged_count = sum(1 for m in media_list if m.category == "geotagged_photos")
        photos_count = sum(1 for m in media_list if m.category == "photos")
        videos_count = sum(1 for m in media_list if m.category == "videos")
        posters_count = sum(1 for m in media_list if m.category == "posters")

        has_firebase = any(m.storage_provider in ("firebase", "local") for m in media_list)
        has_drive = bool(self.linked_drive_folder_id) or any(m.storage_provider == "google_drive" for m in media_list)
        if has_firebase and has_drive:
            storage_source = "both"
        elif has_drive:
            storage_source = "google_drive"
        elif has_firebase:
            storage_source = "firebase"
        else:
            storage_source = "none"

        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "event_date": format_iso_utc(self.event_date) if self.event_date else None,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "created_by": self.created_by,
            "creator_name": self.creator.username if self.creator else None,
            "document_count": self.documents.count() if hasattr(self, "documents") else 0,
            "media_count": len(media_list),
            "geotagged_count": geotagged_count,
            "photos_count": photos_count,
            "videos_count": videos_count,
            "posters_count": posters_count,
            "storage_source": storage_source,
            "linked_drive_folder_id": self.linked_drive_folder_id,
            "linked_drive_folder_name": self.linked_drive_folder_name,
            "drive_web_view_link": self.drive_web_view_link,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_documents:
            data["documents"] = [d.to_dict() for d in self.documents.all()]
        if include_media:
            data["media_files"] = [m.to_dict() for m in media_list]
        return data


class FolderDocument(db.Model):
    """File metadata stored in an event folder, backed by Firebase Cloud Storage or local file."""
    __tablename__ = "folder_documents"

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("event_folders.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False, index=True)
    content_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # in bytes
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    folder = db.relationship("EventFolder", back_populates="documents")
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

    def to_dict(self) -> dict:
        """Serialize document metadata to dictionary."""
        uploader_name = self.uploader.username if self.uploader else None
        return {
            "id": self.id,
            "folder_id": self.folder_id,
            "folder_name": self.folder.name if self.folder else None,
            "original_filename": self.original_filename,
            "file_name": self.original_filename,
            "storage_path": self.storage_path,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "file_size_formatted": self.format_file_size(),
            "uploaded_by": self.uploaded_by,
            "uploaded_by_id": self.uploaded_by,
            "uploader_name": uploader_name,
            "uploaded_by_name": uploader_name,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class ActivityReport(db.Model):
    """Activity report draft and finalized reports generated from the official template."""
    __tablename__ = "activity_reports"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_folder_id = db.Column(db.Integer, db.ForeignKey("event_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = db.Column(db.String(50), default="draft", nullable=False)  # draft, generated, exported
    template_version = db.Column(db.String(50), default="1.0", nullable=False)
    data_json = db.Column(db.Text, nullable=True)  # JSON payload of all section fields
    generated_docx_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    folder = db.relationship("EventFolder", back_populates="reports")
    creator = db.relationship("User", foreign_keys=[created_by])
    team = db.relationship("Team")

    def get_data(self) -> dict:
        """Parse data_json into dictionary safely."""
        if not self.data_json:
            return {}
        try:
            return json.loads(self.data_json)
        except Exception:
            return {}

    def set_data(self, data: dict):
        """Serialize data dictionary into data_json."""
        self.data_json = json.dumps(data) if data else None

    def to_dict(self, include_data: bool = True) -> dict:
        """Serialize activity report to dictionary."""
        creator_name = self.creator.username if self.creator else None
        payload = {
            "id": self.id,
            "title": self.title,
            "event_folder_id": self.event_folder_id,
            "event_folder_name": self.folder.name if self.folder else None,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "created_by": self.created_by,
            "created_by_id": self.created_by,
            "creator_name": creator_name,
            "created_by_name": creator_name,
            "status": self.status,
            "template_version": self.template_version,
            "has_generated_docx": bool(self.generated_docx_path),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_data:
            payload["data"] = self.get_data()
        return payload
