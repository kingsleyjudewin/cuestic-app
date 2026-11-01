import os
import io
import time
import uuid
import base64
import logging
from typing import Optional, BinaryIO
from datetime import datetime
from sqlalchemy.orm import joinedload, defer
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.documentation import EventFolder, FolderDocument, ActivityReport
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.report_generator_service import ReportGeneratorService
from app.services.audit_service import AuditService
from app.utils.errors import ValidationError, NotFoundError, PermissionDeniedError
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


class DocumentationService:
    """Service handling Documentation team folders, document uploads, and report generation."""

    _cached_doc_team_id: Optional[int] = None
    _cached_doc_team_leader_id: Optional[int] = None
    _cached_doc_team_at: float = 0.0

    _cached_reports_data: Optional[list] = None
    _cached_reports_at: float = 0.0

    _cached_folders_data: Optional[list] = None
    _cached_folders_at: float = 0.0

    _cached_report_dict_by_id: dict = {}
    _cached_folder_dict_by_id: dict = {}

    @classmethod
    def invalidate_cache(cls, reports: bool = True, folders: bool = True, report_id: int = None, folder_id: int = None):
        """Invalidate in-memory documentation caches on mutation."""
        if reports:
            cls._cached_reports_data = None
            cls._cached_reports_at = 0.0
        if folders:
            cls._cached_folders_data = None
            cls._cached_folders_at = 0.0
        if report_id is not None:
            cls._cached_report_dict_by_id.pop(report_id, None)
        if folder_id is not None:
            cls._cached_folder_dict_by_id.pop(folder_id, None)

    @classmethod
    def get_documentation_team(cls) -> Team:
        """Fetch the Documentation team with in-memory TTL caching."""
        now = time.time()
        if cls._cached_doc_team_id and (now - cls._cached_doc_team_at < 300):
            try:
                team = db.session.get(Team, cls._cached_doc_team_id)
                if team:
                    return team
            except Exception:
                pass

        team = Team.query.filter(
            (Team.slug == "documentation") | (Team.name.ilike("documentation"))
        ).first()
        if not team:
            raise NotFoundError("Documentation team not found.")
        cls._cached_doc_team_id = team.id
        cls._cached_doc_team_leader_id = team.leader_user_id
        cls._cached_doc_team_at = now
        return team

    @classmethod
    def verify_access(cls, user: User, action_description: str = "this operation"):
        """Verify that user is an Admin, Team Leader of Documentation, or a member of the Documentation team."""
        if user.is_admin():
            return True

        if cls._cached_doc_team_leader_id and cls._cached_doc_team_leader_id == user.id:
            return True

        doc_team = cls.get_documentation_team()
        if doc_team.leader_user_id == user.id:
            return True

        if user.linked_member and user.linked_member.team_id == doc_team.id and user.linked_member.is_active:
            return True

        raise PermissionDeniedError(
            f"You do not have permission to access the Documentation portal or perform {action_description}. "
            "Only authorized Documentation team members and administrators have access."
        )

    # -------------------------------------------------------------------------
    # Event Folder Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_folders_data(cls, user: User) -> list[dict]:
        """Fetch list of folder summaries directly from in-memory cache in sub-millisecond time."""
        cls.verify_access(user, "view event folders")
        now = time.time()
        if cls._cached_folders_data is not None and (now - cls._cached_folders_at < 1800.0):
            return cls._cached_folders_data

        folders = cls.list_folders(user)
        data = [f.to_dict(include_documents=False) for f in folders]
        cls._cached_folders_data = data
        cls._cached_folders_at = now
        return data

    @classmethod
    def get_folder_dict(cls, folder_id: int, user: User) -> dict:
        """Fetch single folder with documents from in-memory cache in sub-millisecond time."""
        cls.verify_access(user, "view this folder")
        cached = cls._cached_folder_dict_by_id.get(folder_id)
        if cached is not None:
            return cached

        folder = cls.get_folder_by_id(folder_id, user)
        data = folder.to_dict(include_documents=True)
        cls._cached_folder_dict_by_id[folder_id] = data
        return data

    @classmethod
    def list_reports_data(cls, user: User) -> list[dict]:
        """Fetch list of report summaries directly from in-memory cache in sub-millisecond time."""
        cls.verify_access(user, "list activity reports")
        now = time.time()
        if cls._cached_reports_data is not None and (now - cls._cached_reports_at < 1800.0):
            return cls._cached_reports_data

        reports = cls.list_reports(user)
        data = [r.to_dict(include_data=False) for r in reports]
        cls._cached_reports_data = data
        cls._cached_reports_at = now
        return data

    @classmethod
    def get_report_dict(cls, report_id: int, user: User) -> dict:
        """Fetch single activity report details from in-memory cache in sub-millisecond time."""
        cls.verify_access(user, "view this activity report")
        cached = cls._cached_report_dict_by_id.get(report_id)
        if cached is not None:
            return cached

        report = cls.get_report_by_id(report_id, user)
        data = report.to_dict(include_data=True)
        cls._cached_report_dict_by_id[report_id] = data
        return data

    # -------------------------------------------------------------------------
    # Event Folder Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_folders(cls, user: User) -> list[EventFolder]:
        cls.verify_access(user, "view event folders")
        doc_team = cls.get_documentation_team()
        return (
            EventFolder.query.options(
                joinedload(EventFolder.creator),
                joinedload(EventFolder.team),
            )
            .filter_by(team_id=doc_team.id)
            .order_by(EventFolder.created_at.desc())
            .all()
        )

    @classmethod
    def create_folder(cls, data: dict, user: User) -> EventFolder:
        cls.verify_access(user, "create an event folder")
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Event folder name is required.", details={"name": ["Cannot be empty."]})

        doc_team = cls.get_documentation_team()

        # Parse event_date if provided
        event_date = None
        raw_date = data.get("event_date")
        if raw_date:
            try:
                event_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                pass

        folder = EventFolder(
            name=name,
            description=data.get("description", "").strip() or None,
            event_date=event_date,
            team_id=doc_team.id,
            created_by=user.id,
        )
        db.session.add(folder)
        db.session.commit()
        cls.invalidate_cache(folders=True)

        AuditService.log_action(
            action="EVENT_FOLDER_CREATED",
            entity_type="EventFolder",
            entity_id=folder.id,
            actor_user_id=user.id,
            details={"name": folder.name, "team_id": folder.team_id}
        )
        return folder

    @classmethod
    def get_folder_by_id(cls, folder_id: int, user: User) -> EventFolder:
        cls.verify_access(user, "view this folder")
        folder = (
            EventFolder.query.options(
                joinedload(EventFolder.creator),
            )
            .filter_by(id=folder_id)
            .first()
        )
        if not folder:
            raise NotFoundError(f"Event folder with ID {folder_id} was not found.")
        return folder

    @classmethod
    def delete_folder(cls, folder_id: int, user: User) -> bool:
        cls.verify_access(user, "delete this folder")
        folder = cls.get_folder_by_id(folder_id, user)

        # Delete all files in folder from storage
        for doc in folder.documents.all():
            try:
                FirebaseStorageService.delete_file(doc.storage_path)
            except Exception as e:
                logger.warning("Error deleting storage file for doc %d: %s", doc.id, e)

        db.session.delete(folder)
        db.session.commit()
        cls.invalidate_cache(folders=True, folder_id=folder_id)

        AuditService.log_action(
            action="EVENT_FOLDER_DELETED",
            entity_type="EventFolder",
            entity_id=folder_id,
            actor_user_id=user.id,
            details={"folder_id": folder_id}
        )
        return True

    # -------------------------------------------------------------------------
    # Document Upload & Storage Operations
    # -------------------------------------------------------------------------
    @classmethod
    def upload_document(
        cls,
        folder_id: int,
        file_obj: BinaryIO,
        filename: str,
        content_type: str,
        user: User
    ) -> FolderDocument:
        cls.verify_access(user, "upload documents")
        folder = cls.get_folder_by_id(folder_id, user)

        upload_meta = FirebaseStorageService.upload_file(
            file_obj=file_obj,
            filename=filename,
            team_id=folder.team_id,
            folder_id=folder.id,
            content_type=content_type,
        )

        document = FolderDocument(
            folder_id=folder.id,
            original_filename=upload_meta["original_filename"],
            storage_path=upload_meta["storage_path"],
            content_type=upload_meta["content_type"],
            file_size=upload_meta["file_size"],
            uploaded_by=user.id,
        )
        db.session.add(document)
        folder.updated_at = utc_now()
        db.session.commit()
        cls.invalidate_cache(folders=True, folder_id=folder.id)

        AuditService.log_action(
            action="DOCUMENT_UPLOADED",
            entity_type="FolderDocument",
            entity_id=document.id,
            actor_user_id=user.id,
            details={"filename": document.original_filename, "folder_id": folder.id}
        )
        return document

    @classmethod
    def get_document_by_id(cls, document_id: int, user: User) -> FolderDocument:
        cls.verify_access(user, "access this document")
        document = db.session.get(FolderDocument, document_id)
        if not document:
            raise NotFoundError(f"Document with ID {document_id} was not found.")
        return document

    @classmethod
    def get_document_bytes(cls, document_id: int, user: User) -> tuple[bytes, str, str]:
        """Returns (file_bytes, filename, content_type)."""
        doc = cls.get_document_by_id(document_id, user)
        bytes_data = FirebaseStorageService.get_file_bytes(doc.storage_path)
        return bytes_data, doc.original_filename, doc.content_type or "application/octet-stream"

    @classmethod
    def list_image_documents(cls, user: User) -> list[dict]:
        """List all image documents from event folders for reference selection."""
        cls.verify_access(user, "browse image documents")
        doc_team = cls.get_documentation_team()

        docs = (
            FolderDocument.query.join(EventFolder)
            .filter(EventFolder.team_id == doc_team.id)
            .filter(
                (FolderDocument.content_type.ilike("image/%")) |
                (FolderDocument.original_filename.ilike("%.png")) |
                (FolderDocument.original_filename.ilike("%.jpg")) |
                (FolderDocument.original_filename.ilike("%.jpeg")) |
                (FolderDocument.original_filename.ilike("%.webp"))
            )
            .order_by(FolderDocument.created_at.desc())
            .all()
        )
        return [d.to_dict() for d in docs]

    @classmethod
    def delete_document(cls, document_id: int, user: User) -> bool:
        cls.verify_access(user, "delete this document")
        doc = cls.get_document_by_id(document_id, user)

        FirebaseStorageService.delete_file(doc.storage_path)
        folder = doc.folder

        db.session.delete(doc)
        if folder:
            folder.updated_at = utc_now()
        db.session.commit()
        cls.invalidate_cache(folders=True, folder_id=folder.id if folder else None)

        AuditService.log_action(
            action="DOCUMENT_DELETED",
            entity_type="FolderDocument",
            entity_id=document_id,
            actor_user_id=user.id,
            details={"document_id": document_id}
        )
        return True

    # -------------------------------------------------------------------------
    # Activity Report Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_reports(cls, user: User) -> list[ActivityReport]:
        cls.verify_access(user, "list activity reports")
        doc_team = cls.get_documentation_team()
        return (
            ActivityReport.query.options(
                defer(ActivityReport.data_json),
                joinedload(ActivityReport.creator),
                joinedload(ActivityReport.folder),
                joinedload(ActivityReport.team),
            )
            .filter_by(team_id=doc_team.id)
            .order_by(ActivityReport.updated_at.desc())
            .all()
        )

    @classmethod
    def create_report(cls, data: dict, user: User) -> ActivityReport:
        cls.verify_access(user, "create an activity report")
        title = (data.get("title") or "Untitled Activity Report").strip()
        doc_team = cls.get_documentation_team()

        folder_id = data.get("event_folder_id")
        if folder_id:
            folder = cls.get_folder_by_id(folder_id, user)
        else:
            folder = None

        report = ActivityReport(
            title=title,
            event_folder_id=folder.id if folder else None,
            team_id=doc_team.id,
            created_by=user.id,
            status="draft",
        )
        report.set_data(data.get("data", {}))
        db.session.add(report)
        db.session.commit()
        cls.invalidate_cache(reports=True)

        AuditService.log_action(
            action="ACTIVITY_REPORT_CREATED",
            entity_type="ActivityReport",
            entity_id=report.id,
            actor_user_id=user.id,
            details={"title": report.title, "report_id": report.id}
        )
        return report

    @classmethod
    def get_report_by_id(cls, report_id: int, user: User) -> ActivityReport:
        cls.verify_access(user, "view this activity report")
        report = (
            ActivityReport.query.options(
                joinedload(ActivityReport.creator),
                joinedload(ActivityReport.folder),
                joinedload(ActivityReport.team),
            )
            .filter_by(id=report_id)
            .first()
        )
        if not report:
            raise NotFoundError(f"Activity report with ID {report_id} was not found.")
        return report

    @classmethod
    def update_report(cls, report_id: int, data: dict, user: User) -> ActivityReport:
        cls.verify_access(user, "update this activity report")
        report = cls.get_report_by_id(report_id, user)

        if "title" in data and data["title"]:
            report.title = data["title"].strip()

        if "event_folder_id" in data:
            report.event_folder_id = data["event_folder_id"]

        if "status" in data:
            report.status = data["status"]

        if "data" in data and isinstance(data["data"], dict):
            report.set_data(data["data"])

        report.updated_at = utc_now()
        db.session.commit()
        cls.invalidate_cache(reports=True, report_id=report_id)
        return report

    @classmethod
    def delete_report(cls, report_id: int, user: User) -> bool:
        cls.verify_access(user, "delete this activity report")
        report = cls.get_report_by_id(report_id, user)

        if report.generated_docx_path and os.path.exists(report.generated_docx_path):
            try:
                os.remove(report.generated_docx_path)
            except Exception:
                pass

        db.session.delete(report)
        db.session.commit()
        cls.invalidate_cache(reports=True, report_id=report_id)
        return True

    @classmethod
    def generate_report_docx(cls, report_id: int, user: User) -> tuple[str, str]:
        """
        Populate the official CUestIC template and generate DOCX file.
        Returns (output_path, download_filename).
        """
        cls.verify_access(user, "generate report document")
        report = cls.get_report_by_id(report_id, user)
        report_data = report.get_data()

        reports_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "instance", "generated_reports")
        )
        os.makedirs(reports_dir, exist_ok=True)

        unique_id = uuid.uuid4().hex[:8]
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in report.title).strip().replace(" ", "_")
        filename = f"{safe_title}_{unique_id}.docx"
        output_filepath = os.path.join(reports_dir, filename)

        # Image resolver reads storage path, base64, downloads, or local file
        def resolve_image(image_ref) -> Optional[bytes]:
            if not image_ref:
                return None
            try:
                # If bytes directly
                if isinstance(image_ref, (bytes, bytearray)):
                    return bytes(image_ref)

                if not isinstance(image_ref, str):
                    return None

                clean_ref = image_ref.strip()
                # If base64 string
                if clean_ref.startswith("data:image") or (len(clean_ref) > 200 and "," in clean_ref[:100]):
                    b64_clean = clean_ref.split(",", 1)[1]
                    return base64.b64decode(b64_clean)
                elif len(clean_ref) > 500 and " " not in clean_ref:
                    try:
                        return base64.b64decode(clean_ref)
                    except Exception:
                        pass

                # If direct existing file path
                if os.path.exists(image_ref):
                    with open(image_ref, "rb") as f:
                        return f.read()

                # If in user Downloads directory (e.g. 3.png)
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", image_ref)
                if os.path.exists(downloads_path):
                    with open(downloads_path, "rb") as f:
                        return f.read()

                # If in instance/uploads
                inst_upload = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "uploads", image_ref))
                if os.path.exists(inst_upload):
                    with open(inst_upload, "rb") as f:
                        return f.read()

                # If matches a FolderDocument record
                doc_record = FolderDocument.query.filter(
                    (FolderDocument.filename == image_ref) | (FolderDocument.storage_path == image_ref)
                ).first()
                if doc_record and doc_record.storage_path:
                    if os.path.exists(doc_record.storage_path):
                        with open(doc_record.storage_path, "rb") as f:
                            return f.read()
                    return FirebaseStorageService.get_file_bytes(doc_record.storage_path)

                # Otherwise from Firebase storage
                return FirebaseStorageService.get_file_bytes(image_ref)
            except Exception as e:
                logger.warning("Could not resolve image %s: %s", image_ref, e)
                return None

        ReportGeneratorService.generate_report_docx(
            report_data=report_data,
            output_filepath=output_filepath,
            image_resolver=resolve_image,
        )

        report.generated_docx_path = output_filepath
        report.status = "generated"
        report.updated_at = utc_now()
        db.session.commit()

        AuditService.log_action(
            action="REPORT_DOCX_GENERATED",
            entity_type="ActivityReport",
            entity_id=report.id,
            actor_user_id=user.id,
            details={"filepath": output_filepath}
        )

        return output_filepath, f"Activity_Report_{safe_title}.docx"
