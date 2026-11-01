import json
from typing import Optional, List, Dict
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class McTemplate(db.Model):
    """Reusable event programme and script structure templates."""
    __tablename__ = "mc_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_public_to_team = db.Column(db.Boolean, default=True, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    creator = db.relationship("User", foreign_keys=[created_by])
    segments = db.relationship(
        "McTemplateSegment",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="McTemplateSegment.sequence_order"
    )

    def to_dict(self, include_segments: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type,
            "description": self.description,
            "created_by": self.created_by,
            "creator_name": self.creator.username if self.creator else None,
            "is_public_to_team": self.is_public_to_team,
            "is_default": self.is_default,
            "segment_count": len(self.segments),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_segments:
            data["segments"] = [s.to_dict() for s in self.segments]
        return data


class McTemplateSegment(db.Model):
    """Individual segment blueprint inside an MC Template."""
    __tablename__ = "mc_template_segments"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("mc_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    sequence_order = db.Column(db.Integer, default=1, nullable=False)
    required_fields_json = db.Column(db.Text, nullable=True)
    optional_fields_json = db.Column(db.Text, nullable=True)
    default_mc_assignment = db.Column(db.String(50), default="MC 1", nullable=False)
    ai_instructions = db.Column(db.Text, nullable=True)
    default_stage_directions = db.Column(db.Text, nullable=True)

    template = db.relationship("McTemplate", back_populates="segments")

    def get_required_fields(self) -> List[str]:
        if not self.required_fields_json:
            return []
        try:
            return json.loads(self.required_fields_json)
        except Exception:
            return []

    def set_required_fields(self, fields: List[str]):
        self.required_fields_json = json.dumps(fields) if fields else None

    def get_optional_fields(self) -> List[str]:
        if not self.optional_fields_json:
            return []
        try:
            return json.loads(self.optional_fields_json)
        except Exception:
            return []

    def set_optional_fields(self, fields: List[str]):
        self.optional_fields_json = json.dumps(fields) if fields else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "segment_type": self.segment_type,
            "title": self.title,
            "sequence_order": self.sequence_order,
            "required_fields": self.get_required_fields(),
            "optional_fields": self.get_optional_fields(),
            "default_mc_assignment": self.default_mc_assignment,
            "ai_instructions": self.ai_instructions,
            "default_stage_directions": self.default_stage_directions,
        }


class McScript(db.Model):
    """Event hosting script model created and managed by the MC Team."""
    __tablename__ = "mc_scripts"

    STATUS_DRAFT = "draft"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_READY_FOR_REVIEW = "ready_for_review"
    STATUS_FINALIZED = "finalized"
    STATUS_SUBMITTED = "ready_for_review"
    STATUS_REVISION_REQUESTED = "revision_requested"
    STATUS_APPROVED = "finalized"
    STATUS_UPLOADED = "uploaded"

    ALL_STATUSES = (
        STATUS_DRAFT,
        STATUS_IN_PROGRESS,
        STATUS_READY_FOR_REVIEW,
        STATUS_FINALIZED,
        STATUS_REVISION_REQUESTED,
        STATUS_UPLOADED,
    )

    TONE_FORMAL = "Formal"
    TONE_SEMI_FORMAL = "Semi-formal"
    TONE_ENERGETIC = "Energetic"
    TONE_CELEBRATORY = "Celebratory"

    ALL_TONES = (TONE_FORMAL, TONE_SEMI_FORMAL, TONE_ENERGETIC, TONE_CELEBRATORY)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("mc_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("event_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = db.Column(db.String(30), default=STATUS_DRAFT, nullable=False, index=True)

    # Event context
    event_type = db.Column(db.String(100), nullable=True)
    venue = db.Column(db.String(200), nullable=True)
    event_date = db.Column(db.DateTime(timezone=True), nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(50), default="English", nullable=False)
    tone = db.Column(db.String(50), default=TONE_FORMAL, nullable=False)
    number_of_anchors = db.Column(db.Integer, default=2, nullable=False)

    # Structured details stored as JSON
    anchors_json = db.Column(db.Text, nullable=True)
    event_metadata_json = db.Column(db.Text, nullable=True)
    chief_guest_details = db.Column(db.Text, nullable=True)
    faculty_speaker_details = db.Column(db.Text, nullable=True)
    event_schedule = db.Column(db.Text, nullable=True)
    segments_json = db.Column(db.Text, nullable=True)
    full_script_content = db.Column(db.Text, nullable=True)

    # Export & Google Drive references
    generated_docx_path = db.Column(db.String(500), nullable=True)
    drive_file_id = db.Column(db.String(255), nullable=True, index=True)
    drive_folder_id = db.Column(db.String(255), nullable=True)
    drive_web_view_link = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    event = db.relationship("Event")
    template = db.relationship("McTemplate", foreign_keys=[template_id])
    task = db.relationship("Task")
    folder = db.relationship("EventFolder", foreign_keys=[folder_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    script_segments = db.relationship(
        "McScriptSegment",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="McScriptSegment.sequence_order"
    )
    reviews = db.relationship(
        "McScriptReview",
        back_populates="script",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="desc(McScriptReview.created_at)"
    )

    def get_anchors(self) -> List[Dict]:
        """Parse anchors_json into structured list."""
        if not self.anchors_json:
            return [
                {"id": 1, "name": "Anchor 1", "role": "Host"},
                {"id": 2, "name": "Anchor 2", "role": "Co-Host"},
            ]
        try:
            parsed = json.loads(self.anchors_json)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def set_anchors(self, anchors: List[Dict]):
        """Serialize anchors list to anchors_json."""
        self.anchors_json = json.dumps(anchors) if anchors else None

    def get_event_metadata(self) -> Dict:
        """Parse event_metadata_json into dict."""
        if not self.event_metadata_json:
            return {}
        try:
            parsed = json.loads(self.event_metadata_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def set_event_metadata(self, metadata: Dict):
        """Serialize event_metadata dict to event_metadata_json."""
        self.event_metadata_json = json.dumps(metadata) if metadata else None

    def get_segments(self) -> List[Dict]:
        """Parse segments from McScriptSegment rows or segments_json fallback."""
        if self.script_segments:
            return [s.to_dict() for s in self.script_segments]
        if not self.segments_json:
            return []
        try:
            parsed = json.loads(self.segments_json)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def set_segments(self, segments: List[Dict]):
        """Serialize segments list to segments_json."""
        self.segments_json = json.dumps(segments) if segments else None

    def to_dict(self, include_segments: bool = True, include_reviews: bool = False) -> dict:
        """Serialize script to dictionary."""
        creator_name = self.creator.username if self.creator else None
        event_name = self.event.name if self.event else None
        task_title = self.task.title if self.task else None
        folder_name = self.folder.name if self.folder else None
        template_name = self.template.name if self.template else None

        segments = self.get_segments() if include_segments else []

        data = {
            "id": self.id,
            "title": self.title,
            "event_id": self.event_id,
            "event_name": event_name,
            "template_id": self.template_id,
            "template_name": template_name,
            "task_id": self.task_id,
            "task_title": task_title,
            "folder_id": self.folder_id,
            "folder_name": folder_name,
            "created_by": self.created_by,
            "creator_name": creator_name,
            "status": self.status,
            "event_type": self.event_type,
            "venue": self.venue,
            "event_date": format_iso_utc(self.event_date) if self.event_date else None,
            "duration": self.duration,
            "language": self.language,
            "tone": self.tone,
            "number_of_anchors": self.number_of_anchors,
            "anchors": self.get_anchors(),
            "event_metadata": self.get_event_metadata(),
            "chief_guest_details": self.chief_guest_details,
            "faculty_speaker_details": self.faculty_speaker_details,
            "event_schedule": self.event_schedule,
            "full_script_content": self.full_script_content,
            "has_generated_docx": bool(self.generated_docx_path),
            "drive_file_id": self.drive_file_id,
            "drive_folder_id": self.drive_folder_id,
            "drive_web_view_link": self.drive_web_view_link,
            "is_uploaded_to_drive": bool(self.drive_file_id),
            "segment_count": len(segments),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }

        if include_segments:
            data["segments"] = segments

        if include_reviews:
            data["reviews"] = [r.to_dict() for r in self.reviews.all()]

        return data


class McScriptSegment(db.Model):
    """Active programme segment inside a live MC Script."""
    __tablename__ = "mc_script_segments"

    id = db.Column(db.Integer, primary_key=True)
    script_id = db.Column(db.Integer, db.ForeignKey("mc_scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    sequence_order = db.Column(db.Integer, default=1, nullable=False)
    assigned_mc = db.Column(db.String(100), default="MC 1", nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    input_data_json = db.Column(db.Text, nullable=True)
    generated_dialogue = db.Column(db.Text, nullable=True)
    stage_directions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    script = db.relationship("McScript", back_populates="script_segments")

    def get_input_data(self) -> Dict:
        if not self.input_data_json:
            return {}
        try:
            parsed = json.loads(self.input_data_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def set_input_data(self, data: Dict):
        self.input_data_json = json.dumps(data) if data else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "script_id": self.script_id,
            "segment_type": self.segment_type,
            "title": self.title,
            "sequence_order": self.sequence_order,
            "assigned_mc": self.assigned_mc,
            "is_enabled": self.is_enabled,
            "input_data": self.get_input_data(),
            "generated_dialogue": self.generated_dialogue or "",
            "stage_directions": self.stage_directions or "",
            "dialogue": self.generated_dialogue or "",  # alias for backward compatibility
            "anchor": self.assigned_mc,                # alias for backward compatibility
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class McScriptReview(db.Model):
    """Review decision and feedback history for MC event hosting scripts."""
    __tablename__ = "mc_script_reviews"

    id = db.Column(db.Integer, primary_key=True)
    script_id = db.Column(db.Integer, db.ForeignKey("mc_scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decision = db.Column(db.String(30), nullable=False)  # "approved", "revision_requested"
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    script = db.relationship("McScript", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])

    def to_dict(self) -> dict:
        """Serialize review to dictionary."""
        return {
            "id": self.id,
            "script_id": self.script_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_name": self.reviewer.username if self.reviewer else None,
            "decision": self.decision,
            "comments": self.comments,
            "created_at": format_iso_utc(self.created_at),
        }


class McDriveFolderMapping(db.Model):
    """Configurable Google Drive destination folders for the MC Team."""
    __tablename__ = "mc_drive_folder_mappings"

    CATEGORIES = [
        "Inauguration Scripts",
        "Event Hosting Scripts",
        "Guest Introductions",
        "Announcements",
        "Vote of Thanks",
        "Final Approved Scripts",
    ]

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(60), unique=True, nullable=False)
    drive_folder_id = db.Column(db.String(255), nullable=True)
    drive_folder_name = db.Column(db.String(255), nullable=True)
    configured_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationship
    configurator = db.relationship("User", foreign_keys=[configured_by])

    def to_dict(self) -> dict:
        """Serialize folder mapping to dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "drive_folder_id": self.drive_folder_id,
            "drive_folder_name": self.drive_folder_name,
            "configured_by": self.configured_by,
            "configurator_name": self.configurator.username if self.configurator else None,
            "updated_at": format_iso_utc(self.updated_at),
        }
