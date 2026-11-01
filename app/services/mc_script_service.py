import os
import io
import re
import json
import time
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from sqlalchemy.orm import joinedload, selectinload
from app.extensions import db
from app.models.mc_script import (
    McScript,
    McScriptSegment,
    McScriptReview,
    McDriveFolderMapping,
    McTemplate,
    McTemplateSegment,
)
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.models.documentation import EventFolder, FolderDocument
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.google_drive_service import GoogleDriveService
from app.services.audit_service import AuditService
from app.utils.datetime_utils import utc_now, format_iso_utc, format_friendly_local
from app.utils.errors import ValidationError, NotFoundError, PermissionDeniedError
from app.services.mc_template_service import DEFAULT_EVENT_STRUCTURES

logger = logging.getLogger(__name__)


def _set_cell_text(
    cell,
    text: str,
    bold: bool = False,
    font_size: int = 11,
    color_rgb: Tuple[int, int, int] = (0, 0, 0),
    italic: bool = False,
):
    """Set text in a table cell with consistent typography."""
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)


class McScriptService:
    """Core business logic for MC Team Script Management, Templates, Segments, Review, and Export."""

    _CACHED_MC_TEAM_ID: Optional[int] = None
    _DASHBOARD_CACHE: Dict[str, Tuple[float, dict]] = {}
    _SCRIPTS_CACHE: Dict[str, Tuple[float, List[dict]]] = {}
    _FOLDERS_CACHE: Dict[str, Tuple[float, List[dict]]] = {}
    _CACHE_TTL: float = 60.0  # 60s cache TTL

    @classmethod
    def clear_caches(cls):
        """Invalidate all in-memory caches upon mutations."""
        cls._DASHBOARD_CACHE.clear()
        cls._SCRIPTS_CACHE.clear()
        cls._FOLDERS_CACHE.clear()

    @classmethod
    def get_or_create_mc_team(cls) -> Team:
        """Retrieve existing MC Team or create it automatically if not found with in-memory ID cache."""
        if cls._CACHED_MC_TEAM_ID is not None:
            team = db.session.get(Team, cls._CACHED_MC_TEAM_ID)
            if team:
                return team

        team = Team.query.filter(
            (Team.slug == "mc") | (Team.name.ilike("%mc%")) | (Team.name.ilike("%master of ceremonies%"))
        ).first()

        if not team:
            team = Team(
                name="MC Team",
                slug="mc",
                description="Master of Ceremonies and Event Hosting Team",
                is_active=True,
            )
            db.session.add(team)
            db.session.commit()
            logger.info("Created MC Team (ID: %s, Slug: %s)", team.id, team.slug)

        cls._CACHED_MC_TEAM_ID = team.id
        return team

    @classmethod
    def is_mc_member_or_lead(cls, user: User) -> bool:
        """Check if user belongs to the MC team or is an administrator."""
        if user.is_admin():
            return True
        if user.linked_member and user.linked_member.team:
            slug = (user.linked_member.team.slug or "").lower()
            name = (user.linked_member.team.name or "").lower()
            if "mc" in slug or "mc" in name or "ceremonies" in name or "anchor" in name:
                return True
        return False

    @classmethod
    def is_mc_lead(cls, user: User) -> bool:
        """Check if user has lead or administrator authority over MC scripts."""
        if user.is_admin():
            return True
        if user.role == User.ROLE_TEAM_LEADER:
            if user.linked_member and user.linked_member.team:
                slug = (user.linked_member.team.slug or "").lower()
                name = (user.linked_member.team.name or "").lower()
                if "mc" in slug or "mc" in name or "ceremonies" in name:
                    return True
        return False

    # -------------------------------------------------------------------------
    # Dashboard & Summary
    # -------------------------------------------------------------------------
    @classmethod
    def get_dashboard_summary(cls, user: User) -> dict:
        """Compile comprehensive dashboard counters and upcoming schedule for the MC Team with sub-ms in-memory caching."""
        now_ts = time.time()
        cache_key = f"{user.id}_{cls.is_mc_lead(user)}"
        cached = cls._DASHBOARD_CACHE.get(cache_key)
        if cached and (now_ts - cached[0] < cls._CACHE_TTL):
            return cached[1]

        now = utc_now()

        # Assigned events/tasks query (count only)
        if user.linked_member:
            assigned_task_count = TaskAssignment.query.filter(TaskAssignment.member_id == user.linked_member.id).count()
        else:
            assigned_task_count = 0

        # Script counts by status - Single GROUP BY SQL query instead of 4 sequential count round-trips
        status_query = db.session.query(McScript.status, db.func.count(McScript.id))
        if not cls.is_mc_lead(user):
            status_query = status_query.filter(McScript.created_by == user.id)
        status_map = dict(status_query.group_by(McScript.status).all())

        in_progress_count = (
            status_map.get(McScript.STATUS_IN_PROGRESS, 0)
            + status_map.get(McScript.STATUS_DRAFT, 0)
            + status_map.get(McScript.STATUS_REVISION_REQUESTED, 0)
        )
        awaiting_review_count = (
            status_map.get(McScript.STATUS_READY_FOR_REVIEW, 0)
            + status_map.get("submitted", 0)
        )
        approved_count = (
            status_map.get(McScript.STATUS_FINALIZED, 0)
            + status_map.get("approved", 0)
        )
        uploaded_count = status_map.get(McScript.STATUS_UPLOADED, 0)

        # Upcoming events (next 30 days)
        upcoming_events = (
            Event.query.filter(Event.start_at >= now)
            .order_by(Event.start_at.asc())
            .limit(5)
            .all()
        )

        # Eager load relations for recent scripts
        scripts_base = McScript.query.options(
            joinedload(McScript.creator),
            joinedload(McScript.event),
            joinedload(McScript.task),
            joinedload(McScript.folder),
            joinedload(McScript.template),
        )
        if not cls.is_mc_lead(user):
            scripts_base = scripts_base.filter(McScript.created_by == user.id)

        recent_scripts = scripts_base.order_by(McScript.updated_at.desc()).limit(6).all()

        res = {
            "assigned_events_count": assigned_task_count,
            "scripts_in_progress": in_progress_count,
            "scripts_awaiting_review": awaiting_review_count,
            "approved_scripts": approved_count,
            "recently_uploaded_scripts": uploaded_count,
            "upcoming_events": [e.to_dict() for e in upcoming_events],
            "recent_scripts": [s.to_dict(include_segments=False) for s in recent_scripts],
            "is_lead_or_admin": cls.is_mc_lead(user),
        }
        cls._DASHBOARD_CACHE[cache_key] = (now_ts, res)
        return res

    # -------------------------------------------------------------------------
    # Script CRUD Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_scripts(
        cls,
        user: User,
        status: Optional[str] = None,
        event_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        search_query: Optional[str] = None,
    ) -> List[dict]:
        """List scripts filtered by status, event, folder, or search text with eager loading and caching."""
        now_ts = time.time()
        cache_key = f"{user.id}_{status or ''}_{event_id or ''}_{folder_id or ''}_{search_query or ''}"
        cached = cls._SCRIPTS_CACHE.get(cache_key)
        if cached and (now_ts - cached[0] < cls._CACHE_TTL):
            return cached[1]

        query = McScript.query.options(
            joinedload(McScript.creator),
            joinedload(McScript.event),
            joinedload(McScript.task),
            joinedload(McScript.folder),
            joinedload(McScript.template),
        )

        if status:
            if status == "ready_for_review":
                query = query.filter(McScript.status.in_([McScript.STATUS_READY_FOR_REVIEW, McScript.STATUS_SUBMITTED]))
            elif status == "finalized":
                query = query.filter(McScript.status.in_([McScript.STATUS_FINALIZED, McScript.STATUS_APPROVED, McScript.STATUS_UPLOADED]))
            elif status == "in_progress":
                query = query.filter(McScript.status.in_([McScript.STATUS_IN_PROGRESS, McScript.STATUS_REVISION_REQUESTED]))
            else:
                query = query.filter(McScript.status == status)

        if event_id:
            query = query.filter(McScript.event_id == event_id)

        if folder_id:
            query = query.filter(McScript.folder_id == folder_id)

        if search_query:
            clean = f"%{search_query.strip()}%"
            query = query.filter(
                (McScript.title.ilike(clean)) |
                (McScript.venue.ilike(clean)) |
                (McScript.event_type.ilike(clean))
            )

        # Non-leads only see their own scripts or finalized/uploaded scripts
        if not cls.is_mc_lead(user):
            query = query.filter(
                (McScript.created_by == user.id) |
                (McScript.status.in_([McScript.STATUS_FINALIZED, McScript.STATUS_APPROVED, McScript.STATUS_UPLOADED]))
            )

        scripts = query.order_by(McScript.updated_at.desc()).all()
        res = [s.to_dict(include_segments=False) for s in scripts]
        cls._SCRIPTS_CACHE[cache_key] = (now_ts, res)
        return res

    @classmethod
    def get_script_by_id(cls, script_id: int, user: User) -> McScript:
        """Fetch script and verify view permissions with eager loading."""
        script = (
            McScript.query.options(
                joinedload(McScript.creator),
                joinedload(McScript.event),
                joinedload(McScript.task),
                joinedload(McScript.folder),
                joinedload(McScript.template),
                selectinload(McScript.script_segments),
            )
            .filter_by(id=script_id)
            .first()
        )
        if not script:
            raise NotFoundError(f"MC Script with ID {script_id} was not found.")

        # Permission check
        if not cls.is_mc_lead(user) and script.created_by != user.id and script.status not in (McScript.STATUS_FINALIZED, McScript.STATUS_APPROVED, McScript.STATUS_UPLOADED):
            raise PermissionDeniedError("You do not have permission to view this script draft.")

        return script

    @classmethod
    def create_script(cls, data: dict, user: User) -> McScript:
        """
        Create a new event hosting script draft with optional template or event-type blueprints.
        """
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("Script title is required.", details={"title": ["Required"]})

        event_id = data.get("event_id")
        template_id = data.get("template_id")
        task_id = data.get("task_id")
        folder_id = data.get("folder_id")
        event_date = None
        if data.get("event_date"):
            try:
                event_date = datetime.fromisoformat(str(data["event_date"]).replace("Z", "+00:00"))
            except Exception:
                pass

        # If event_id is supplied, pre-fill missing metadata from event
        if event_id:
            evt = db.session.get(Event, event_id)
            if evt:
                if not data.get("venue"):
                    data["venue"] = evt.location
                if not event_date:
                    event_date = evt.start_at

        event_type = data.get("event_type") or "Department Event"
        anchors = data.get("anchors") or [
            {"id": 1, "name": "MC 1", "role": "Lead Anchor"},
            {"id": 2, "name": "MC 2", "role": "Co-Anchor"},
        ]

        script = McScript(
            title=title,
            event_id=event_id,
            template_id=template_id,
            task_id=task_id,
            folder_id=folder_id,
            created_by=user.id,
            status=McScript.STATUS_DRAFT,
            event_type=event_type,
            venue=data.get("venue"),
            event_date=event_date,
            duration=data.get("duration") or "2 Hours",
            language=data.get("language") or "English",
            tone=data.get("tone") or McScript.TONE_FORMAL,
            number_of_anchors=len(anchors),
            chief_guest_details=data.get("chief_guest_details"),
            faculty_speaker_details=data.get("faculty_speaker_details"),
            event_schedule=data.get("event_schedule"),
            full_script_content=data.get("full_script_content"),
        )
        script.set_anchors(anchors)

        if data.get("event_metadata"):
            script.set_event_metadata(data["event_metadata"])

        db.session.add(script)
        db.session.flush()

        # Populate Programme Segments
        # Strategy 1: User provided custom segments in creation payload
        if data.get("segments") and isinstance(data["segments"], list):
            for idx, s in enumerate(data["segments"], start=1):
                seg = McScriptSegment(
                    script_id=script.id,
                    segment_type=s.get("segment_type", "custom"),
                    title=s.get("title", f"Segment {idx}"),
                    sequence_order=idx,
                    assigned_mc=s.get("assigned_mc") or s.get("anchor") or anchors[0]["name"],
                    is_enabled=s.get("is_enabled", True),
                    generated_dialogue=s.get("dialogue") or s.get("generated_dialogue"),
                    stage_directions=s.get("stage_direction") or s.get("stage_directions"),
                )
                if s.get("input_data"):
                    seg.set_input_data(s["input_data"])
                db.session.add(seg)

        # Strategy 2: Pre-populate from McTemplate
        elif template_id:
            template = db.session.get(McTemplate, template_id)
            if template:
                for idx, t_seg in enumerate(template.segments, start=1):
                    # Default MC allocation (alternate between Anchor 1 & Anchor 2)
                    default_mc = anchors[0]["name"]
                    if t_seg.default_mc_assignment in ("MC 2", "Anchor 2") and len(anchors) > 1:
                        default_mc = anchors[1]["name"]

                    seg = McScriptSegment(
                        script_id=script.id,
                        segment_type=t_seg.segment_type,
                        title=t_seg.title,
                        sequence_order=idx,
                        assigned_mc=default_mc,
                        is_enabled=True,
                        stage_directions=t_seg.default_stage_directions,
                    )
                    db.session.add(seg)

        # Strategy 3: Pre-populate from default Event Type blueprint
        elif event_type in DEFAULT_EVENT_STRUCTURES:
            blueprint = DEFAULT_EVENT_STRUCTURES[event_type]
            for idx, s in enumerate(blueprint["segments"], start=1):
                default_mc = anchors[0]["name"]
                if s.get("default_mc_assignment") in ("MC 2", "Anchor 2") and len(anchors) > 1:
                    default_mc = anchors[1]["name"]

                seg = McScriptSegment(
                    script_id=script.id,
                    segment_type=s["segment_type"],
                    title=s["title"],
                    sequence_order=idx,
                    assigned_mc=default_mc,
                    is_enabled=True,
                    stage_directions=s.get("default_stage_directions"),
                )
                db.session.add(seg)

        db.session.commit()
        cls.clear_caches()

        AuditService.log_action(
            action="MC_SCRIPT_CREATE",
            entity_type="McScript",
            entity_id=script.id,
            actor_user_id=user.id,
            details={"title": script.title, "event_id": script.event_id, "template_id": template_id}
        )
        logger.info("Created MC Script ID %s by user %s", script.id, user.username)
        return script

    @classmethod
    def update_script(cls, script_id: int, data: dict, user: User) -> McScript:
        """Update script metadata, event context, and anchors."""
        script = cls.get_script_by_id(script_id, user)

        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("Only the author or an MC Lead can edit this script.")

        if "title" in data and str(data["title"]).strip():
            script.title = str(data["title"]).strip()
        if "folder_id" in data:
            script.folder_id = data["folder_id"]
        if "template_id" in data:
            script.template_id = data["template_id"]
        if "event_type" in data:
            script.event_type = data["event_type"]
        if "venue" in data:
            script.venue = data["venue"]
        if "duration" in data:
            script.duration = data["duration"]
        if "language" in data:
            script.language = data["language"]
        if "tone" in data:
            script.tone = data["tone"]
        if "status" in data:
            script.status = data["status"]
        if "number_of_anchors" in data:
            script.number_of_anchors = int(data["number_of_anchors"])
        if "chief_guest_details" in data:
            script.chief_guest_details = data["chief_guest_details"]
        if "faculty_speaker_details" in data:
            script.faculty_speaker_details = data["faculty_speaker_details"]
        if "event_schedule" in data:
            script.event_schedule = data["event_schedule"]
        if "full_script_content" in data:
            script.full_script_content = data["full_script_content"]

        if "anchors" in data:
            script.set_anchors(data["anchors"])
        if "event_metadata" in data:
            script.set_event_metadata(data["event_metadata"])

        if script.status == McScript.STATUS_REVISION_REQUESTED:
            script.status = McScript.STATUS_IN_PROGRESS

        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return script

    @classmethod
    def delete_script(cls, script_id: int, user: User) -> bool:
        """Delete script draft."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to delete this script.")

        db.session.delete(script)
        db.session.commit()
        cls.clear_caches()
        return True

    # -------------------------------------------------------------------------
    # Visual Programme Segment Operations
    # -------------------------------------------------------------------------
    @classmethod
    def add_segment(cls, script_id: int, data: dict, user: User) -> dict:
        """Add a new segment card to the script's programme structure."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this script.")

        max_order = (
            db.session.query(db.func.max(McScriptSegment.sequence_order))
            .filter_by(script_id=script.id)
            .scalar()
            or 0
        )

        title = (data.get("title") or "New Programme Segment").strip()
        segment_type = data.get("segment_type") or "custom"
        assigned_mc = data.get("assigned_mc") or (script.get_anchors()[0]["name"] if script.get_anchors() else "MC 1")

        seg = McScriptSegment(
            script_id=script.id,
            segment_type=segment_type,
            title=title,
            sequence_order=max_order + 1,
            assigned_mc=assigned_mc,
            is_enabled=data.get("is_enabled", True),
            generated_dialogue=data.get("dialogue") or data.get("generated_dialogue"),
            stage_directions=data.get("stage_directions") or data.get("stage_direction"),
        )
        if data.get("input_data"):
            seg.set_input_data(data["input_data"])

        db.session.add(seg)
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return seg.to_dict()

    @classmethod
    def update_segment(cls, script_id: int, segment_id: int, data: dict, user: User) -> dict:
        """Update an existing segment's dialogue, stage cues, inputs, or assigned MC."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this segment.")

        seg = McScriptSegment.query.filter_by(id=segment_id, script_id=script.id).first()
        if not seg:
            raise NotFoundError(f"Segment ID {segment_id} was not found on script {script_id}.")

        if "title" in data and str(data["title"]).strip():
            seg.title = str(data["title"]).strip()
        if "segment_type" in data:
            seg.segment_type = data["segment_type"]
        if "assigned_mc" in data:
            seg.assigned_mc = data["assigned_mc"]
        if "is_enabled" in data:
            seg.is_enabled = bool(data["is_enabled"])
        if "dialogue" in data or "generated_dialogue" in data:
            seg.generated_dialogue = data.get("dialogue") or data.get("generated_dialogue")
        if "stage_directions" in data or "stage_direction" in data:
            seg.stage_directions = data.get("stage_directions") or data.get("stage_direction")
        if "input_data" in data and isinstance(data["input_data"], dict):
            seg.set_input_data(data["input_data"])

        seg.updated_at = utc_now()
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return seg.to_dict()

    @classmethod
    def duplicate_segment(cls, script_id: int, segment_id: int, user: User) -> dict:
        """Duplicate a segment and insert it immediately after the original."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this script.")

        source = McScriptSegment.query.filter_by(id=segment_id, script_id=script.id).first()
        if not source:
            raise NotFoundError(f"Segment ID {segment_id} not found.")

        # Shift subsequent segments down by 1
        subsequent = (
            McScriptSegment.query.filter(
                McScriptSegment.script_id == script.id,
                McScriptSegment.sequence_order > source.sequence_order,
            )
            .order_by(McScriptSegment.sequence_order.desc())
            .all()
        )
        for s in subsequent:
            s.sequence_order += 1

        clone = McScriptSegment(
            script_id=script.id,
            segment_type=source.segment_type,
            title=f"{source.title} (Copy)",
            sequence_order=source.sequence_order + 1,
            assigned_mc=source.assigned_mc,
            is_enabled=source.is_enabled,
            input_data_json=source.input_data_json,
            generated_dialogue=source.generated_dialogue,
            stage_directions=source.stage_directions,
        )
        db.session.add(clone)
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return clone.to_dict()

    @classmethod
    def delete_segment(cls, script_id: int, segment_id: int, user: User) -> bool:
        """Delete segment and re-sequence remaining segments."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this script.")

        seg = McScriptSegment.query.filter_by(id=segment_id, script_id=script.id).first()
        if not seg:
            raise NotFoundError(f"Segment ID {segment_id} not found.")

        deleted_order = seg.sequence_order
        db.session.delete(seg)

        # Shift down remaining
        remaining = (
            McScriptSegment.query.filter(
                McScriptSegment.script_id == script.id,
                McScriptSegment.sequence_order > deleted_order,
            )
            .order_by(McScriptSegment.sequence_order.asc())
            .all()
        )
        for r in remaining:
            r.sequence_order -= 1

        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return True

    @classmethod
    def reorder_segments(cls, script_id: int, ordered_segment_ids: List[int], user: User) -> List[dict]:
        """Reorder entire programme sequence according to visual builder drag-and-drop."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this script.")

        segments = McScriptSegment.query.filter_by(script_id=script.id).all()
        seg_map = {s.id: s for s in segments}

        for idx, sid in enumerate(ordered_segment_ids, start=1):
            if sid in seg_map:
                seg_map[sid].sequence_order = idx

        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()

        updated = (
            McScriptSegment.query.filter_by(script_id=script.id)
            .order_by(McScriptSegment.sequence_order.asc())
            .all()
        )
        return [s.to_dict() for s in updated]

    @classmethod
    def auto_assign_mcs(cls, script_id: int, user: User) -> List[dict]:
        """Automatically alternate dialogue assignment (MC 1 / MC 2) across enabled segments."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("You do not have permission to edit this script.")

        anchors = script.get_anchors()
        if not anchors:
            anchors = [{"name": "MC 1"}, {"name": "MC 2"}]

        segments = (
            McScriptSegment.query.filter_by(script_id=script.id)
            .order_by(McScriptSegment.sequence_order.asc())
            .all()
        )

        active_idx = 0
        for s in segments:
            if s.is_enabled:
                assigned = anchors[active_idx % len(anchors)]["name"]
                s.assigned_mc = assigned
                active_idx += 1

        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return [s.to_dict() for s in segments]

    @classmethod
    def validate_script(cls, script_id: int, user: User) -> dict:
        """
        Perform pre-flight verification on the entire MC script before finalization.
        Checks event title, anchor setup, empty segment dialogue, speaker bios, and placeholders.
        """
        script = cls.get_script_by_id(script_id, user)
        errors: List[str] = []
        warnings: List[str] = []

        if not script.title or len(script.title.strip()) < 3:
            errors.append("Script title is missing or too short.")

        if not script.venue:
            warnings.append("Event venue is not specified.")

        if not script.event_date:
            warnings.append("Event date is not set.")

        anchors = script.get_anchors()
        if not anchors:
            errors.append("At least one MC anchor must be defined.")

        segments = (
            McScriptSegment.query.filter_by(script_id=script.id)
            .order_by(McScriptSegment.sequence_order.asc())
            .all()
        )
        if not segments:
            errors.append("Script has no programme segments. Add segments using the Programme Builder.")

        filled_segments = 0
        for s in segments:
            if not s.is_enabled:
                continue

            if not s.generated_dialogue or len(s.generated_dialogue.strip()) < 5:
                warnings.append(f"Segment '{s.title}' has empty or incomplete spoken dialogue.")
            else:
                filled_segments += 1
                # Check for lingering placeholders
                if re.search(r"\[(Insert|TBD|Name|______)", s.generated_dialogue, re.IGNORECASE):
                    warnings.append(f"Segment '{s.title}' contains unfilled bracketed placeholders (e.g. [Insert ...]).")

            # Segment-specific validation checks
            data = s.get_input_data()
            if s.segment_type == "speaker_introduction":
                if not data.get("speaker_name"):
                    warnings.append(f"Speaker Introduction segment '{s.title}' does not have a speaker name.")
            elif s.segment_type == "prize_distribution":
                if not data.get("competitions"):
                    warnings.append(f"Prize Distribution segment '{s.title}' does not have any competitions or winners entered.")

        total_enabled = sum(1 for s in segments if s.is_enabled)
        completion_pct = int((filled_segments / total_enabled * 100)) if total_enabled > 0 else 0

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "completion_percentage": completion_pct,
            "total_segments": len(segments),
            "enabled_segments": total_enabled,
            "script_status": script.status,
        }

    # -------------------------------------------------------------------------
    # Review & Approval Workflow
    # -------------------------------------------------------------------------
    @classmethod
    def submit_for_review(cls, script_id: int, user: User) -> McScript:
        """Submit script draft for review by MC Team Leader or Administrator."""
        script = cls.get_script_by_id(script_id, user)
        if script.created_by != user.id and not cls.is_mc_lead(user):
            raise PermissionDeniedError("Only the author can submit this script.")

        script.status = McScript.STATUS_READY_FOR_REVIEW
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return script

    @classmethod
    def review_script(cls, script_id: int, decision: str, comments: Optional[str], user: User) -> McScript:
        """Approve or request revisions on an MC script draft."""
        if not cls.is_mc_lead(user):
            raise PermissionDeniedError("Only MC Team Leaders or Administrators can approve or review scripts.")

        script = cls.get_script_by_id(script_id, user)
        clean_dec = decision.strip().lower()

        if clean_dec in ("approved", "finalized"):
            script.status = McScript.STATUS_FINALIZED
        elif clean_dec == "revision_requested":
            script.status = McScript.STATUS_REVISION_REQUESTED
        else:
            raise ValidationError(f"Invalid review decision '{decision}'. Use 'approved' or 'revision_requested'.")

        review = McScriptReview(
            script_id=script.id,
            reviewer_id=user.id,
            decision=clean_dec,
            comments=comments,
        )
        db.session.add(review)
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return script

    # -------------------------------------------------------------------------
    # Stage-Ready DOCX Export Generation
    # -------------------------------------------------------------------------
    @classmethod
    def generate_docx(cls, script_id: int, user: User) -> Tuple[str, str]:
        """
        Generate a comprehensive, stage-ready DOCX document modeled directly after
        the IEEE Tech Talk and SOURCE CODE Valedictory reference scripts.
        """
        script = cls.get_script_by_id(script_id, user)
        meta = script.get_event_metadata()
        anchors = script.get_anchors()

        doc = docx.Document()

        # Set 0.75-inch margins for optimal stage teleprompter width
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        # 1. Header / Title Block
        p_dept = doc.add_paragraph()
        p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_dept.paragraph_format.space_after = Pt(2)
        r_dept = p_dept.add_run(
            meta.get("organizing_department")
            or "DEPARTMENT OF ELECTRONICS AND COMMUNICATION ENGINEERING"
        )
        r_dept.font.name = "Calibri"
        r_dept.font.size = Pt(11)
        r_dept.font.bold = True
        r_dept.font.color.rgb = RGBColor(70, 70, 70)

        p_club = doc.add_paragraph()
        p_club.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_club.paragraph_format.space_after = Pt(6)
        r_club = p_club.add_run(
            meta.get("organizing_club")
            or "CUESTIC CLUB & IEEE STUDENT BRANCH"
        )
        r_club.font.name = "Calibri"
        r_club.font.size = Pt(10)
        r_club.font.bold = True
        r_club.font.color.rgb = RGBColor(18, 53, 91)

        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title.paragraph_format.space_before = Pt(4)
        p_title.paragraph_format.space_after = Pt(4)
        r_title = p_title.add_run(f"{script.title.upper()} – MASTER SCRIPT")
        r_title.font.name = "Calibri"
        r_title.font.size = Pt(18)
        r_title.font.bold = True
        r_title.font.color.rgb = RGBColor(18, 53, 91)

        # Sub-header: Date, Venue, Time, Tone
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_p.paragraph_format.space_after = Pt(14)
        date_str = format_friendly_local(script.event_date) if script.event_date else "Upcoming Date"
        r_sub = sub_p.add_run(
            f"Venue: {script.venue or 'Auditorium'} | Date: {date_str} | Tone: {script.tone} | Status: {script.status.upper()}"
        )
        r_sub.font.name = "Calibri"
        r_sub.font.size = Pt(10)
        r_sub.font.italic = True
        r_sub.font.color.rgb = RGBColor(100, 100, 100)

        # 2. MC Anchor Roster Table
        roster_table = doc.add_table(rows=1, cols=3)
        roster_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        roster_table.autofit = False
        hdr_cells = roster_table.rows[0].cells
        _set_cell_text(hdr_cells[0], "Anchor Role", bold=True, color_rgb=(255, 255, 255))
        _set_cell_text(hdr_cells[1], "Anchor Name", bold=True, color_rgb=(255, 255, 255))
        _set_cell_text(hdr_cells[2], "Responsibility", bold=True, color_rgb=(255, 255, 255))
        for c in hdr_cells:
            c._tc.get_or_add_tcPr().append(docx.oxml.parse_xml(r'<w:shd {} w:fill="12355B"/>'.format(docx.oxml.ns.nsdecls('w'))))

        for a in anchors:
            row = roster_table.add_row().cells
            _set_cell_text(row[0], f"MC {a.get('id', 1)}", bold=True)
            _set_cell_text(row[1], a.get("name", "Anchor"))
            _set_cell_text(row[2], a.get("role", "Host"))

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

        # 3. Programme Timeline & Overview Table
        segments = (
            McScriptSegment.query.filter_by(script_id=script.id)
            .order_by(McScriptSegment.sequence_order.asc())
            .all()
        )
        if not segments:
            # Fallback to segments_json
            legacy = script.get_segments()
            segments = []
            for idx, l in enumerate(legacy, start=1):
                s = McScriptSegment(
                    script_id=script.id,
                    segment_type=l.get("segment_type", "custom"),
                    title=l.get("title", f"Segment {idx}"),
                    sequence_order=idx,
                    assigned_mc=l.get("anchor") or l.get("assigned_mc") or "MC 1",
                    generated_dialogue=l.get("dialogue"),
                    stage_directions=l.get("stage_direction"),
                )
                segments.append(s)

        p_ov = doc.add_paragraph()
        p_ov.paragraph_format.space_before = Pt(8)
        p_ov.paragraph_format.space_after = Pt(4)
        r_ov = p_ov.add_run("PROGRAMME TIMELINE & FLOW")
        r_ov.font.name = "Calibri"
        r_ov.font.size = Pt(12)
        r_ov.font.bold = True
        r_ov.font.color.rgb = RGBColor(18, 53, 91)

        flow_table = doc.add_table(rows=1, cols=4)
        flow_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        flow_table.autofit = False
        f_hdrs = flow_table.rows[0].cells
        _set_cell_text(f_hdrs[0], "#", bold=True, color_rgb=(255, 255, 255))
        _set_cell_text(f_hdrs[1], "Segment Title", bold=True, color_rgb=(255, 255, 255))
        _set_cell_text(f_hdrs[2], "Type", bold=True, color_rgb=(255, 255, 255))
        _set_cell_text(f_hdrs[3], "Assigned MC", bold=True, color_rgb=(255, 255, 255))
        for c in f_hdrs:
            c._tc.get_or_add_tcPr().append(docx.oxml.parse_xml(r'<w:shd {} w:fill="12355B"/>'.format(docx.oxml.ns.nsdecls('w'))))

        for s in segments:
            row = flow_table.add_row().cells
            _set_cell_text(row[0], str(s.sequence_order), bold=True)
            _set_cell_text(row[1], s.title)
            _set_cell_text(row[2], s.segment_type.replace("_", " ").title())
            _set_cell_text(row[3], s.assigned_mc, bold=True, color_rgb=(0, 51, 102))

        doc.add_page_break()

        # 4. Master Stage Dialogue & Directions
        p_scr = doc.add_paragraph()
        p_scr.paragraph_format.space_after = Pt(8)
        r_scr = p_scr.add_run("STAGE SCRIPT — DIALOGUE & CUES")
        r_scr.font.name = "Calibri"
        r_scr.font.size = Pt(14)
        r_scr.font.bold = True
        r_scr.font.color.rgb = RGBColor(18, 53, 91)

        # Distinguish MC colors for reading on stage
        color_palette = [
            (0, 51, 102),     # Dark Navy
            (102, 0, 102),    # Deep Purple
            (0, 102, 102),    # Teal
            (153, 51, 0),     # Dark Amber
        ]

        for s in segments:
            if not s.is_enabled:
                continue

            # Heading for segment
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(4)
            r_h = h.add_run(f"{s.sequence_order}. {s.title.upper()}")
            r_h.font.name = "Calibri"
            r_h.font.size = Pt(12)
            r_h.font.bold = True
            r_h.font.color.rgb = RGBColor(18, 53, 91)

            # Stage Direction
            if s.stage_directions:
                sd_p = doc.add_paragraph()
                sd_p.paragraph_format.space_before = Pt(2)
                sd_p.paragraph_format.space_after = Pt(4)
                r_sd = sd_p.add_run(f"{s.stage_directions}")
                r_sd.font.name = "Calibri"
                r_sd.font.size = Pt(10)
                r_sd.font.italic = True
                r_sd.font.color.rgb = RGBColor(140, 70, 0)

            # Structured Content Tables if present (Winners or Badges)
            data = s.get_input_data()
            if s.segment_type == "prize_distribution" and data.get("competitions"):
                for c in data["competitions"]:
                    cp = doc.add_paragraph()
                    cp.paragraph_format.space_before = Pt(4)
                    cp.paragraph_format.space_after = Pt(2)
                    rc = cp.add_run(f"Competition: {c.get('competition_name', 'Event')}")
                    rc.font.bold = True
                    rc.font.size = Pt(10)

                    w_table = doc.add_table(rows=1, cols=3)
                    w_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                    w_hdrs = w_table.rows[0].cells
                    _set_cell_text(w_hdrs[0], "Position", bold=True, font_size=9)
                    _set_cell_text(w_hdrs[1], "Winners", bold=True, font_size=9)
                    _set_cell_text(w_hdrs[2], "Team", bold=True, font_size=9)
                    for w in c.get("winners", []):
                        r = w_table.add_row().cells
                        _set_cell_text(r[0], w.get("position", ""), bold=True, font_size=9)
                        _set_cell_text(r[1], w.get("winner_names", ""), font_size=9)
                        _set_cell_text(r[2], w.get("team_name", ""), font_size=9)

            elif s.segment_type == "badge_distribution" and data.get("recipients"):
                b_table = doc.add_table(rows=1, cols=3)
                b_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                b_hdrs = b_table.rows[0].cells
                _set_cell_text(b_hdrs[0], "Role / Wing", bold=True, font_size=9)
                _set_cell_text(b_hdrs[1], "Recipient Name", bold=True, font_size=9)
                _set_cell_text(b_hdrs[2], "Status", bold=True, font_size=9)
                for rec in data["recipients"]:
                    r = b_table.add_row().cells
                    _set_cell_text(r[0], rec.get("role_title", ""), bold=True, font_size=9)
                    _set_cell_text(r[1], rec.get("name", ""), font_size=9)
                    _set_cell_text(r[2], "Badge Presented", font_size=9, italic=True)

            # Spoken Dialogue
            dial = s.generated_dialogue or ""
            dial_p = doc.add_paragraph()
            dial_p.paragraph_format.space_before = Pt(4)
            dial_p.paragraph_format.space_after = Pt(8)
            dial_p.paragraph_format.line_spacing = 1.25

            # Speaker Label
            assigned_label = s.assigned_mc or "MC"
            r_spk = dial_p.add_run(f"({assigned_label}):\n")
            r_spk.font.name = "Calibri"
            r_spk.font.size = Pt(11)
            r_spk.font.bold = True
            r_spk.font.color.rgb = RGBColor(0, 51, 102)

            r_txt = dial_p.add_run(dial)
            r_txt.font.name = "Calibri"
            r_txt.font.size = Pt(11)

        # Output directory
        output_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "instance", "generated_scripts")
        )
        os.makedirs(output_dir, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in script.title).strip().replace(" ", "_")
        filename = f"MC_Script_{safe_title}_{script.id}.docx"
        out_path = os.path.join(output_dir, filename)

        doc.save(out_path)
        script.generated_docx_path = out_path
        db.session.commit()

        logger.info("Generated MC Script DOCX at: %s", out_path)
        return out_path, filename

    # -------------------------------------------------------------------------
    # Google Drive Upload Workflow
    # -------------------------------------------------------------------------
    @classmethod
    def upload_to_google_drive(cls, script_id: int, user: User, target_category: str = "Final Approved Scripts") -> dict:
        """Upload finalized hosting script to Google Drive."""
        script = cls.get_script_by_id(script_id, user)

        if not script.generated_docx_path or not os.path.exists(script.generated_docx_path):
            cls.generate_docx(script_id, user)

        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in script.title).strip().replace(" ", "_")
        upload_name = f"MC_Script_{safe_title}.docx"

        folder_mapping = McDriveFolderMapping.query.filter_by(category=target_category).first()
        target_folder_id = folder_mapping.drive_folder_id if folder_mapping else None

        if not target_folder_id:
            try:
                folders = GoogleDriveService.list_folders(user.id, query="MC Team")
                if folders:
                    target_folder_id = folders[0]["id"]
                else:
                    created_f = GoogleDriveService.create_folder(user.id, "MC Team")
                    target_folder_id = created_f["id"]
            except Exception as e:
                logger.warning("Could not auto-locate MC Team Drive folder: %s", e)

        if not target_folder_id:
            raise ValidationError("No Google Drive folder configured for MC Team.")

        with open(script.generated_docx_path, "rb") as f:
            drive_meta = GoogleDriveService.upload_file_to_drive(
                user_id=user.id,
                drive_folder_id=target_folder_id,
                file_obj=f,
                filename=upload_name,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        script.drive_file_id = drive_meta["id"]
        script.drive_web_view_link = drive_meta.get("web_view_link")
        script.drive_folder_id = target_folder_id
        script.status = McScript.STATUS_UPLOADED
        script.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()

        AuditService.log_action(
            action="MC_SCRIPT_DRIVE_UPLOAD",
            entity_type="McScript",
            entity_id=script.id,
            actor_user_id=user.id,
            details={"drive_file_id": script.drive_file_id, "folder_id": target_folder_id}
        )
        return {
            "script_id": script.id,
            "drive_file_id": script.drive_file_id,
            "drive_web_view_link": script.drive_web_view_link,
            "status": "uploaded",
        }

    # -------------------------------------------------------------------------
    # Folders & Document Uploads
    # -------------------------------------------------------------------------
    @classmethod
    def list_folders(cls, user: User) -> List[dict]:
        """List folders belonging to the MC Team with grouped count optimization and caching."""
        now_ts = time.time()
        cached = cls._FOLDERS_CACHE.get("all")
        if cached and (now_ts - cached[0] < cls._CACHE_TTL):
            return cached[1]

        team = cls.get_or_create_mc_team()
        folders = EventFolder.query.filter(EventFolder.team_id == team.id).order_by(EventFolder.created_at.desc()).all()

        script_counts = dict(
            db.session.query(McScript.folder_id, db.func.count(McScript.id))
            .filter(McScript.folder_id.isnot(None))
            .group_by(McScript.folder_id)
            .all()
        )

        result = []
        for f in folders:
            fd = f.to_dict()
            fd["script_count"] = script_counts.get(f.id, 0)
            result.append(fd)

        cls._FOLDERS_CACHE["all"] = (now_ts, result)
        return result

    @classmethod
    def create_folder(cls, data: dict, user: User) -> dict:
        """Create a new folder for the MC Team."""
        team = cls.get_or_create_mc_team()
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Folder name is required.", details={"name": ["Required"]})

        event_date = None
        if data.get("event_date"):
            try:
                event_date = datetime.fromisoformat(str(data["event_date"]).replace("Z", "+00:00"))
            except Exception:
                pass

        drive_link = data.get("drive_link") or data.get("drive_web_view_link")
        drive_folder_id = data.get("drive_folder_id") or data.get("linked_drive_folder_id")

        folder = EventFolder(
            name=name,
            description=data.get("description"),
            event_date=event_date,
            team_id=team.id,
            created_by=user.id,
            linked_drive_folder_id=drive_folder_id,
            drive_web_view_link=drive_link,
        )
        db.session.add(folder)
        db.session.commit()
        cls.clear_caches()
        fd = folder.to_dict()
        fd["script_count"] = 0
        return fd

    @classmethod
    def update_folder(cls, folder_id: int, data: dict, user: User) -> dict:
        """Update MC folder name, description, or Google Drive link."""
        team = cls.get_or_create_mc_team()
        folder = db.session.get(EventFolder, folder_id)
        if not folder or (folder.team_id != team.id and not user.is_admin()):
            raise NotFoundError(f"Folder with ID {folder_id} was not found.")

        if "name" in data and str(data["name"]).strip():
            folder.name = str(data["name"]).strip()
        if "description" in data:
            folder.description = data["description"]
        if "drive_link" in data or "drive_web_view_link" in data:
            folder.drive_web_view_link = data.get("drive_link") or data.get("drive_web_view_link")
        if "drive_folder_id" in data or "linked_drive_folder_id" in data:
            folder.linked_drive_folder_id = data.get("drive_folder_id") or data.get("linked_drive_folder_id")
        folder.updated_at = utc_now()
        db.session.commit()
        cls.clear_caches()
        return folder.to_dict()

    @classmethod
    def get_folder(cls, folder_id: int, user: User) -> dict:
        """Retrieve folder details with uploaded script files and script drafts."""
        team = cls.get_or_create_mc_team()
        folder = db.session.get(EventFolder, folder_id)
        if not folder or (folder.team_id != team.id and not user.is_admin()):
            raise NotFoundError(f"Folder with ID {folder_id} was not found.")

        folder_dict = folder.to_dict(include_documents=True)
        scripts = (
            McScript.query.options(
                joinedload(McScript.creator),
                joinedload(McScript.event),
                joinedload(McScript.task),
                joinedload(McScript.folder),
                joinedload(McScript.template),
            )
            .filter(McScript.folder_id == folder.id)
            .order_by(McScript.updated_at.desc())
            .all()
        )
        folder_dict["scripts"] = [s.to_dict(include_segments=False) for s in scripts]
        folder_dict["script_count"] = len(scripts)
        return folder_dict

    @classmethod
    def delete_folder(cls, folder_id: int, user: User) -> bool:
        """Delete an MC folder."""
        team = cls.get_or_create_mc_team()
        folder = db.session.get(EventFolder, folder_id)
        if not folder or (folder.team_id != team.id and not user.is_admin()):
            raise NotFoundError(f"Folder with ID {folder_id} was not found.")

        McScript.query.filter(McScript.folder_id == folder_id).update({"folder_id": None})

        for doc in folder.documents.all():
            try:
                FirebaseStorageService.delete_file(doc.storage_path)
            except Exception:
                pass

        db.session.delete(folder)
        db.session.commit()
        cls.clear_caches()
        return True

    @classmethod
    def upload_script_to_folder(cls, folder_id: int, file_obj, filename: str, content_type: str, user: User) -> dict:
        """Upload a script file to an MC folder."""
        team = cls.get_or_create_mc_team()
        folder = db.session.get(EventFolder, folder_id)
        if not folder or (folder.team_id != team.id and not user.is_admin()):
            raise NotFoundError(f"Folder with ID {folder_id} was not found.")

        upload_meta = FirebaseStorageService.upload_file(
            file_obj=file_obj,
            filename=filename,
            team_id=team.id,
            folder_id=folder.id,
            content_type=content_type,
        )

        doc = FolderDocument(
            folder_id=folder.id,
            original_filename=upload_meta["original_filename"],
            storage_path=upload_meta["storage_path"],
            content_type=upload_meta["content_type"],
            file_size=upload_meta["file_size"],
            uploaded_by=user.id,
        )
        db.session.add(doc)

        clean_title = os.path.splitext(filename)[0].replace("_", " ").title()
        script = McScript(
            title=clean_title,
            folder_id=folder.id,
            created_by=user.id,
            status=McScript.STATUS_IN_PROGRESS,
            generated_docx_path=upload_meta["storage_path"] if filename.lower().endswith(".docx") else None,
        )
        db.session.add(script)
        db.session.commit()
        cls.clear_caches()

        return {
            "document": doc.to_dict(),
            "script": script.to_dict(include_segments=False),
        }

    @classmethod
    def get_document_bytes(cls, doc_id: int, user: User) -> tuple[bytes, str, str]:
        """Download uploaded script document bytes."""
        doc = db.session.get(FolderDocument, doc_id)
        if not doc:
            raise NotFoundError(f"Document with ID {doc_id} was not found.")
        bytes_data = FirebaseStorageService.get_file_bytes(doc.storage_path)
        return bytes_data, doc.original_filename, doc.content_type or "application/octet-stream"

    @classmethod
    def delete_document(cls, doc_id: int, user: User) -> bool:
        """Delete uploaded script document."""
        doc = db.session.get(FolderDocument, doc_id)
        if not doc:
            raise NotFoundError(f"Document with ID {doc_id} was not found.")
        try:
            FirebaseStorageService.delete_file(doc.storage_path)
        except Exception:
            pass
        db.session.delete(doc)
        db.session.commit()
        return True

    @classmethod
    def get_team_members(cls, user: User) -> List[dict]:
        """Get members of the MC team for task assignment."""
        team = cls.get_or_create_mc_team()
        members = Member.query.filter(Member.team_id == team.id, Member.is_active == True).all()
        return [
            {
                "id": m.id,
                "full_name": m.full_name,
                "email": m.email,
                "phone_number": m.phone_number,
                "role": m.role,
                "is_leader": m.role == Member.ROLE_TEAM_LEADER,
            }
            for m in members
        ]

    @classmethod
    def assign_task_to_member(cls, task_id: int, member_id: int, user: User) -> dict:
        """Assign or delegate an existing task to an MC team member."""
        from app.services.task_service import TaskService
        new_assignments = TaskService.add_assignments_to_task(
            task_id=task_id,
            member_ids=[member_id],
            actor_user=user,
        )
        return new_assignments[0].to_dict() if new_assignments else {}
