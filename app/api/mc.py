import io
import os
import time
import logging
from typing import Optional, List
from flask import Blueprint, request, g, send_file
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.services.mc_script_service import McScriptService
from app.services.mc_template_service import McTemplateService
from app.services.mc_ai_service import MCAssistantService
from app.services.ai_service import AIService, AIProviderNotConfiguredError
from app.services.google_drive_service import GoogleDriveService
from app.models.event import Event
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.mc_script import McScript, McScriptSegment
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError, NotFoundError

logger = logging.getLogger(__name__)

mc_bp = Blueprint("mc", __name__)

_MY_TASKS_CACHE: dict = {}
_EVENTS_CACHE: tuple = (0.0, [])
_CACHE_TTL = 30.0  # 30 seconds

def clear_task_cache():
    _MY_TASKS_CACHE.clear()


# -----------------------------------------------------------------------------
# Dashboard & Event Integration
# -----------------------------------------------------------------------------
@mc_bp.route("/dashboard", methods=["GET"])
@token_required
def get_dashboard():
    """Retrieve MC Team dashboard summary metrics, upcoming events, and active scripts."""
    data = McScriptService.get_dashboard_summary(g.current_user)
    return success_response(data=data)


@mc_bp.route("/events", methods=["GET"])
@token_required
def list_available_events():
    """List existing club events to populate script details and prevent re-entering data (cached)."""
    global _EVENTS_CACHE
    now_ts = time.time()
    if _EVENTS_CACHE[1] and (now_ts - _EVENTS_CACHE[0] < _CACHE_TTL):
        return success_response(data=_EVENTS_CACHE[1])

    events = Event.query.order_by(Event.start_at.desc()).all()
    data = [e.to_dict() for e in events]
    _EVENTS_CACHE = (now_ts, data)
    return success_response(data=data)


@mc_bp.route("/my-tasks", methods=["GET"])
@token_required
def get_my_tasks():
    """Retrieve event and script tasks assigned to the authenticated MC member with batch script resolution and caching."""
    user = g.current_user
    now_ts = time.time()
    cache_key = str(user.id)
    cached = _MY_TASKS_CACHE.get(cache_key)
    if cached and (now_ts - cached[0] < _CACHE_TTL):
        return success_response(data=cached[1])

    query = TaskAssignment.query.options(
        joinedload(TaskAssignment.task).joinedload(Task.event),
        joinedload(TaskAssignment.member),
    )

    if user.linked_member:
        query = query.filter(TaskAssignment.member_id == user.linked_member.id)
    else:
        query = query.filter(TaskAssignment.assigned_by == user.id)

    assignments = query.order_by(TaskAssignment.assigned_at.desc()).all()

    # Pre-fetch all linked scripts in a single batch query instead of N queries
    task_ids = [a.task_id for a in assignments if a.task_id]
    event_ids = [a.task.event_id for a in assignments if a.task and a.task.event_id]

    filters = []
    if task_ids:
        filters.append(McScript.task_id.in_(task_ids))
    if event_ids:
        filters.append(McScript.event_id.in_(event_ids))

    scripts = McScript.query.filter(db.or_(*filters)).all() if filters else []
    script_by_task = {s.task_id: s for s in scripts if s.task_id}
    script_by_event = {s.event_id: s for s in scripts if s.event_id}

    tasks_data = []
    for a in assignments:
        td = a.to_dict()
        script = script_by_task.get(a.task_id) or (script_by_event.get(a.task.event_id) if a.task else None)
        td["linked_script_id"] = script.id if script else None
        td["linked_script_title"] = script.title if script else None
        td["linked_script_status"] = script.status if script else None
        tasks_data.append(td)

    _MY_TASKS_CACHE[cache_key] = (now_ts, tasks_data)
    return success_response(data=tasks_data)


# -----------------------------------------------------------------------------
# Scripts CRUD Endpoints
# -----------------------------------------------------------------------------
@mc_bp.route("/scripts", methods=["GET"])
@token_required
def list_scripts():
    """List MC scripts with optional status, event, or keyword filters."""
    status = request.args.get("status")
    event_id = request.args.get("event_id", type=int)
    folder_id = request.args.get("folder_id", type=int)
    search_q = request.args.get("q")

    scripts = McScriptService.list_scripts(
        user=g.current_user,
        status=status,
        event_id=event_id,
        folder_id=folder_id,
        search_query=search_q,
    )
    return success_response(data=scripts)


@mc_bp.route("/scripts", methods=["POST"])
@token_required
def create_script():
    """Create a new event hosting script draft."""
    data = request.get_json(silent=True) or {}
    script = McScriptService.create_script(data, g.current_user)
    return success_response(
        data=script.to_dict(include_segments=True, include_reviews=True),
        message="MC script draft created successfully.",
        status_code=201
    )


@mc_bp.route("/scripts/<int:script_id>", methods=["GET"])
@token_required
def get_script(script_id: int):
    """Get full script details, segments, anchors, and review history."""
    script = McScriptService.get_script_by_id(script_id, g.current_user)
    return success_response(data=script.to_dict(include_segments=True, include_reviews=True))


@mc_bp.route("/scripts/<int:script_id>", methods=["PUT", "PATCH"])
@token_required
def update_script(script_id: int):
    """Save changes to an existing script or update segment dialogues."""
    data = request.get_json(silent=True) or {}
    script = McScriptService.update_script(script_id, data, g.current_user)
    return success_response(
        data=script.to_dict(include_segments=True, include_reviews=True),
        message="MC script saved successfully."
    )


@mc_bp.route("/scripts/<int:script_id>", methods=["DELETE"])
@token_required
def delete_script(script_id: int):
    """Delete an MC script draft."""
    McScriptService.delete_script(script_id, g.current_user)
    return success_response(message="MC script deleted successfully.")


# -----------------------------------------------------------------------------
# Review & Approval Endpoints
# -----------------------------------------------------------------------------
@mc_bp.route("/scripts/<int:script_id>/submit", methods=["POST"])
@token_required
def submit_for_review(script_id: int):
    """Submit script for review by the MC Lead."""
    script = McScriptService.submit_for_review(script_id, g.current_user)
    return success_response(
        data=script.to_dict(include_segments=True, include_reviews=True),
        message="Script submitted for review successfully."
    )


@mc_bp.route("/scripts/<int:script_id>/review", methods=["POST"])
@token_required
def review_script(script_id: int):
    """Review script: approve or request revisions."""
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    comments = data.get("comments")

    if not decision:
        raise ValidationError("Review decision is required.", details={"decision": ["Required"]})

    script = McScriptService.review_script(
        script_id=script_id,
        decision=decision,
        comments=comments,
        user=g.current_user,
    )
    return success_response(
        data=script.to_dict(include_segments=True, include_reviews=True),
        message=f"Script marked as '{script.status}'."
    )


# -----------------------------------------------------------------------------
# DOCX Export & Google Drive Upload
# -----------------------------------------------------------------------------
@mc_bp.route("/scripts/<int:script_id>/generate-docx", methods=["POST"])
@token_required
def generate_docx(script_id: int):
    """Generate professional DOCX version of the script."""
    out_path, filename = McScriptService.generate_docx(script_id, g.current_user)
    return success_response(
        data={"script_id": script_id, "filename": filename, "status": "generated"},
        message="Hosting script DOCX generated successfully."
    )


@mc_bp.route("/scripts/<int:script_id>/download-docx", methods=["GET"])
@token_required
def download_docx(script_id: int):
    """Download the generated DOCX file."""
    script = McScriptService.get_script_by_id(script_id, g.current_user)
    if not script.generated_docx_path or not os.path.exists(script.generated_docx_path):
        McScriptService.generate_docx(script_id, g.current_user)

    safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in script.title).strip().replace(" ", "_")
    download_name = f"MC_Script_{safe_title}.docx"

    return send_file(
        script.generated_docx_path,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=download_name,
    )


@mc_bp.route("/scripts/<int:script_id>/upload-drive", methods=["POST"])
@token_required
def upload_to_drive(script_id: int):
    """Upload finalized script to Google Drive."""
    data = request.get_json(silent=True) or {}
    category = data.get("category") or "Final Approved Scripts"

    result = McScriptService.upload_to_google_drive(script_id, g.current_user, target_category=category)
    return success_response(
        data=result,
        message="MC Script uploaded to Google Drive successfully."
    )


# -----------------------------------------------------------------------------
# AI MC Assistant Endpoints
# -----------------------------------------------------------------------------
@mc_bp.route("/ai/generate-script", methods=["POST"])
@token_required
def ai_generate_full_script():
    """Generate a complete event hosting script based on verified event information."""
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    model = data.get("model")

    try:
        result = MCAssistantService.generate_full_script(
            event_info=data,
            provider_name=provider,
            model_name=model,
        )
        return success_response(data=result, message="AI MC hosting script generated successfully.")
    except AIProviderNotConfiguredError as e:
        return success_response(
            data={"segments": [], "full_script": "", "notice": str(e), "is_configured": False},
            message=str(e),
            status_code=200,
        )


@mc_bp.route("/ai/generate-segment", methods=["POST"])
@token_required
def ai_generate_segment():
    """Generate or enhance a specific script segment (e.g., Welcome, Chief Guest, Vote of Thanks)."""
    data = request.get_json(silent=True) or {}
    segment_type = data.get("segment_type") or "welcome"
    event_info = data.get("event_info") or {}
    current_content = data.get("current_content")
    instructions = data.get("instructions")
    provider = data.get("provider")
    model = data.get("model")

    try:
        result = MCAssistantService.generate_segment(
            segment_type=segment_type,
            event_info=event_info,
            current_content=current_content,
            custom_instructions=instructions,
            provider_name=provider,
            model_name=model,
        )
        return success_response(data=result, message="Segment generated successfully.")
    except AIProviderNotConfiguredError as e:
        return success_response(
            data={"segment": None, "notice": str(e), "is_configured": False},
            message=str(e),
            status_code=200,
        )


@mc_bp.route("/ai/rewrite", methods=["POST"])
@token_required
def ai_rewrite_dialogue():
    """Adjust script tone, polish grammar, or auto-insert stage directions."""
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    target_tone = data.get("tone") or "Formal"
    action = data.get("action") or "adjust_tone"
    provider = data.get("provider")
    model = data.get("model")

    if not text.strip():
        raise ValidationError("Text to rewrite is required.", details={"text": ["Required"]})

    try:
        result = MCAssistantService.rewrite_or_adjust_tone(
            text=text,
            target_tone=target_tone,
            action=action,
            provider_name=provider,
            model_name=model,
        )
        return success_response(data=result, message="Dialogue rewritten successfully.")
    except AIProviderNotConfiguredError as e:
        return success_response(
            data={"improved_text": text, "notice": str(e), "is_configured": False},
            message=str(e),
            status_code=200,
        )


@mc_bp.route("/ai-assist", methods=["POST"])
@token_required
def ai_assist():
    """Unified AI copilot assist for MC hosting scripts and event speeches."""
    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction") or ""
    action = data.get("action") or "draft"
    provider = data.get("provider")
    model = data.get("model")

    system_prompt = (
        "You are the CUestIC Department Club Master of Ceremonies (MC) and Event Hosting AI Copilot. "
        "Your role is to craft engaging, professional, and well-structured event hosting scripts, "
        "welcome addresses, dignitary introductions, stage transitions, audience engagement lines, "
        "and vote of thanks for college department events. Maintain accurate placeholders for names, "
        "and format dialogues with Anchor 1 and Anchor 2 cues and clear stage directions."
    )

    try:
        if AIService.is_configured(provider):
            generated, used_provider, used_model = AIService.generate_with_resilient_fallback(
                prompt=f"Task: {action.upper()}\nInstructions: {instruction}",
                system_instruction=system_prompt,
                provider_name=provider,
                model_name=model,
            )
            return success_response(data={"generated_text": generated, "provider": used_provider, "model": used_model})
        else:
            res = MCAssistantService.generate_full_script({"title": instruction, "event_type": "Department Event"})
            return success_response(data={"generated_text": res.get("full_script", ""), "provider": "local_mc_assistant"})
    except Exception as e:
        res = MCAssistantService.generate_full_script({"title": instruction, "event_type": "Department Event"})
        return success_response(data={"generated_text": res.get("full_script", ""), "provider": "local_mc_assistant", "fallback_reason": str(e)})


# -----------------------------------------------------------------------------
# Google Drive Connection Status & Folders
# -----------------------------------------------------------------------------
@mc_bp.route("/drive/status", methods=["GET"])
@token_required
def get_drive_status():
    """Check status of Google Drive integration for MC Team storage."""
    status = GoogleDriveService.get_connection_status(g.current_user.id)
    return success_response(data=status)


@mc_bp.route("/drive/folders", methods=["GET"])
@token_required
def list_drive_folders():
    """List Google Drive folders for destination selection."""
    query = request.args.get("q")
    try:
        folders = GoogleDriveService.list_folders(g.current_user.id, query=query)
        return success_response(data=folders)
    except Exception as e:
        return success_response(data=[], message=f"Notice: {e}")


# -----------------------------------------------------------------------------
# MC Team Event Folders & Document Uploads
# -----------------------------------------------------------------------------
@mc_bp.route("/folders", methods=["GET"])
@token_required
def list_folders():
    """List all folders for MC Team."""
    folders = McScriptService.list_folders(g.current_user)
    return success_response(data=folders)


@mc_bp.route("/folders", methods=["POST"])
@token_required
def create_folder():
    """Create a new folder for the MC Team."""
    data = request.get_json(silent=True) or {}
    folder = McScriptService.create_folder(data, g.current_user)
    return success_response(data=folder, message="Folder created successfully.", status_code=201)


@mc_bp.route("/folders/<int:folder_id>", methods=["GET"])
@token_required
def get_folder(folder_id: int):
    """Retrieve an MC folder with uploaded files and scripts."""
    folder = McScriptService.get_folder(folder_id, g.current_user)
    return success_response(data=folder)


@mc_bp.route("/folders/<int:folder_id>", methods=["PUT", "PATCH"])
@token_required
def update_folder(folder_id: int):
    """Update MC folder metadata, name, description, or Google Drive link."""
    data = request.get_json(silent=True) or {}
    folder = McScriptService.update_folder(folder_id, data, g.current_user)
    return success_response(data=folder, message="Folder updated successfully.")


@mc_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
@token_required
def delete_folder(folder_id: int):
    """Delete an MC folder."""
    McScriptService.delete_folder(folder_id, g.current_user)
    return success_response(message="Folder deleted successfully.")


@mc_bp.route("/folders/<int:folder_id>/upload", methods=["POST"])
@token_required
def upload_script(folder_id: int):
    """Upload a script file (DOCX, PDF, TXT) to an MC folder."""
    if "file" not in request.files:
        raise ValidationError("No file provided in multipart upload.", details={"file": ["Required"]})

    file = request.files["file"]
    if not file.filename:
        raise ValidationError("Selected file has an empty filename.")

    content_type = file.content_type or "application/octet-stream"
    result = McScriptService.upload_script_to_folder(
        folder_id=folder_id,
        file_obj=file.stream,
        filename=file.filename,
        content_type=content_type,
        user=g.current_user,
    )
    return success_response(data=result, message="Script uploaded successfully.", status_code=201)


@mc_bp.route("/documents/<int:document_id>/download", methods=["GET"])
@token_required
def download_document(document_id: int):
    """Download an uploaded script document."""
    bytes_data, filename, content_type = McScriptService.get_document_bytes(document_id, g.current_user)
    return send_file(
        io.BytesIO(bytes_data),
        mimetype=content_type,
        as_attachment=True,
        download_name=filename,
    )


@mc_bp.route("/documents/<int:document_id>", methods=["DELETE"])
@token_required
def delete_document(document_id: int):
    """Delete an uploaded script document."""
    McScriptService.delete_document(document_id, g.current_user)
    return success_response(message="Document deleted successfully.")


# -----------------------------------------------------------------------------
# MC Team Members & Task Assignment
# -----------------------------------------------------------------------------
@mc_bp.route("/team-members", methods=["GET"])
@token_required
def list_team_members():
    """List members in the MC Team for delegation/assignment."""
    members = McScriptService.get_team_members(g.current_user)
    return success_response(data=members)


@mc_bp.route("/tasks/<int:task_id>/assign", methods=["POST"])
@token_required
def assign_task_to_member(task_id: int):
    """Assign or delegate a task to an MC team member."""
    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    if not member_id:
        raise ValidationError("member_id is required.", details={"member_id": ["Required"]})

    assignment = McScriptService.assign_task_to_member(task_id, int(member_id), g.current_user)
    clear_task_cache()
    return success_response(data=assignment, message="Task assigned successfully.", status_code=201)


# -----------------------------------------------------------------------------
# MC Templates & Event Types Catalog
# -----------------------------------------------------------------------------
@mc_bp.route("/event-types", methods=["GET"])
@token_required
def get_event_types():
    """Get the 15 supported event types catalog with suggested programme structures."""
    catalog = McTemplateService.get_event_types_catalog()
    return success_response(data=catalog)


@mc_bp.route("/templates", methods=["GET"])
@token_required
def list_templates():
    """List MC templates (seeded standard blueprints + user-created templates)."""
    event_type = request.args.get("event_type")
    templates = McTemplateService.list_templates(g.current_user, event_type=event_type)
    return success_response(data=templates)


@mc_bp.route("/templates", methods=["POST"])
@token_required
def create_template():
    """Create a new reusable MC programme template."""
    data = request.get_json(silent=True) or {}
    template = McTemplateService.create_template(data, g.current_user)
    return success_response(data=template.to_dict(), message="Template created successfully.", status_code=201)


@mc_bp.route("/templates/<int:template_id>", methods=["GET"])
@token_required
def get_template(template_id: int):
    """Get template details with all segments."""
    template = McTemplateService.get_template(template_id, g.current_user)
    return success_response(data=template.to_dict())


@mc_bp.route("/templates/<int:template_id>", methods=["PUT", "PATCH"])
@token_required
def update_template(template_id: int):
    """Update a reusable MC template."""
    data = request.get_json(silent=True) or {}
    template = McTemplateService.update_template(template_id, data, g.current_user)
    return success_response(data=template.to_dict(), message="Template updated successfully.")


@mc_bp.route("/templates/<int:template_id>", methods=["DELETE"])
@token_required
def delete_template(template_id: int):
    """Delete a custom MC template."""
    McTemplateService.delete_template(template_id, g.current_user)
    return success_response(message="Template deleted successfully.")


# -----------------------------------------------------------------------------
# Visual Programme Segment Operations
# -----------------------------------------------------------------------------
@mc_bp.route("/scripts/<int:script_id>/segments", methods=["POST"])
@token_required
def add_script_segment(script_id: int):
    """Add a new segment card to the programme builder."""
    data = request.get_json(silent=True) or {}
    seg = McScriptService.add_segment(script_id, data, g.current_user)
    return success_response(data=seg, message="Segment added successfully.", status_code=201)


@mc_bp.route("/scripts/<int:script_id>/segments/<int:segment_id>", methods=["PUT", "PATCH"])
@token_required
def update_script_segment(script_id: int, segment_id: int):
    """Update a programme segment's dialogue, stage directions, inputs, or assigned MC."""
    data = request.get_json(silent=True) or {}
    seg = McScriptService.update_segment(script_id, segment_id, data, g.current_user)
    return success_response(data=seg, message="Segment updated successfully.")


@mc_bp.route("/scripts/<int:script_id>/segments/<int:segment_id>", methods=["DELETE"])
@token_required
def delete_script_segment(script_id: int, segment_id: int):
    """Delete a segment from the programme builder."""
    McScriptService.delete_segment(script_id, segment_id, g.current_user)
    return success_response(message="Segment deleted successfully.")


@mc_bp.route("/scripts/<int:script_id>/segments/<int:segment_id>/duplicate", methods=["POST"])
@token_required
def duplicate_script_segment(script_id: int, segment_id: int):
    """Duplicate a segment and insert it immediately after."""
    seg = McScriptService.duplicate_segment(script_id, segment_id, g.current_user)
    return success_response(data=seg, message="Segment duplicated successfully.", status_code=201)


@mc_bp.route("/scripts/<int:script_id>/segments/reorder", methods=["POST"])
@token_required
def reorder_script_segments(script_id: int):
    """Reorder entire programme sequence according to visual builder drag-and-drop."""
    data = request.get_json(silent=True) or {}
    segment_ids = data.get("segment_ids") or data.get("ordered_ids") or []
    if not segment_ids:
        raise ValidationError("segment_ids list is required.", details={"segment_ids": ["Required"]})

    updated = McScriptService.reorder_segments(script_id, segment_ids, g.current_user)
    return success_response(data=updated, message="Programme segments reordered successfully.")


@mc_bp.route("/scripts/<int:script_id>/auto-assign-mcs", methods=["POST"])
@token_required
def auto_assign_mcs(script_id: int):
    """Automatically alternate dialogue assignment (MC 1 / MC 2) across enabled segments."""
    updated = McScriptService.auto_assign_mcs(script_id, g.current_user)
    return success_response(data=updated, message="Anchors auto-assigned successfully.")


@mc_bp.route("/scripts/<int:script_id>/validate", methods=["POST", "GET"])
@token_required
def validate_script(script_id: int):
    """Perform pre-flight verification on the script before stage teleprompter / DOCX export."""
    res = McScriptService.validate_script(script_id, g.current_user)
    return success_response(data=res)


@mc_bp.route("/scripts/<int:script_id>/save-as-template", methods=["POST"])
@token_required
def save_script_as_template(script_id: int):
    """Save an entire script's programme structure as a reusable blueprint."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    description = data.get("description")
    if not name:
        raise ValidationError("Template name is required.", details={"name": ["Required"]})

    template = McTemplateService.save_script_as_template(script_id, name, description, g.current_user)
    data = template if isinstance(template, dict) else template.to_dict()
    return success_response(data=data, message="Script saved as reusable template successfully.", status_code=201)


@mc_bp.route("/scripts/<int:script_id>/segments/<int:segment_id>/ai-generate", methods=["POST"])
@token_required
def ai_generate_script_segment(script_id: int, segment_id: int):
    """
    AI-powered generation/refinement of a specific programme segment.
    Takes into account preceding segment, succeeding segment, event metadata, tone, and action.
    """
    script = McScriptService.get_script_by_id(script_id, g.current_user)
    seg = McScriptSegment.query.filter_by(id=segment_id, script_id=script.id).first()
    if not seg:
        raise NotFoundError(f"Segment ID {segment_id} not found.")

    data = request.get_json(silent=True) or {}
    action = data.get("action") or "generate"
    user_prompt = data.get("instruction") or data.get("user_prompt")
    provider = data.get("provider")
    model = data.get("model")
    input_data = data.get("input_data")

    # If updated input_data provided, update segment immediately
    if input_data and isinstance(input_data, dict):
        seg.set_input_data(input_data)
        db.session.commit()

    # Find previous and next enabled segments for context
    prev_seg = (
        McScriptSegment.query.filter(
            McScriptSegment.script_id == script.id,
            McScriptSegment.sequence_order < seg.sequence_order,
            McScriptSegment.is_enabled == True,
        )
        .order_by(McScriptSegment.sequence_order.desc())
        .first()
    )

    next_seg = (
        McScriptSegment.query.filter(
            McScriptSegment.script_id == script.id,
            McScriptSegment.sequence_order > seg.sequence_order,
            McScriptSegment.is_enabled == True,
        )
        .order_by(McScriptSegment.sequence_order.asc())
        .first()
    )

    event_info = {
        "event_name": script.title,
        "title": script.title,
        "event_type": script.event_type,
        "venue": script.venue,
        "event_date": script.event_date.isoformat() if script.event_date else None,
        "tone": script.tone,
        "organizing_department": script.get_event_metadata().get("organizing_department") or "Department of Electronics and Communication Engineering",
        "organizing_club": script.get_event_metadata().get("organizing_club") or "CUestIC",
        "anchors": script.get_anchors(),
        **(script.get_event_metadata() or {}),
    }

    segment_info = seg.to_dict()

    result = MCAssistantService.generate_segment_dialogue(
        segment_type=seg.segment_type,
        event_info=event_info,
        segment_info=segment_info,
        prev_segment=prev_seg.to_dict() if prev_seg else None,
        next_segment=next_seg.to_dict() if next_seg else None,
        action=action,
        current_dialogue=seg.generated_dialogue,
        current_stage_directions=seg.stage_directions,
        user_prompt=user_prompt,
        provider_name=provider,
        model_name=model,
    )

    apply_to_segment = data.get("apply", True)
    if apply_to_segment and result.get("dialogue"):
        seg.generated_dialogue = result["dialogue"]
        if result.get("stage_directions"):
            seg.stage_directions = result["stage_directions"]
        db.session.commit()

    return success_response(
        data={"segment": seg.to_dict(), "result": result},
        message="Segment generated successfully."
    )


