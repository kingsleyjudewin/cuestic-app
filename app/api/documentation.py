import io
import os
import base64
import logging
from typing import Optional
from flask import Blueprint, request, g, send_file, Response
from app.services.documentation_service import DocumentationService
from app.services.attendance_ocr_service import AttendanceOCRService
from app.services.feedback_analysis_service import FeedbackAnalysisService
from app.services.simulation_service import SimulationService
from app.models.member import Member
from app.services.ai_service import AIService, AIProviderNotConfiguredError, optimize_image_bytes, optimize_base64_image
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError

logger = logging.getLogger(__name__)

documentation_bp = Blueprint("documentation", __name__)


# -----------------------------------------------------------------------------
# Event Folders Endpoints
# -----------------------------------------------------------------------------
@documentation_bp.route("/folders", methods=["GET"])
@token_required
def list_folders():
    """List all event folders for Documentation team."""
    data = DocumentationService.list_folders_data(g.current_user)
    return success_response(data=data)


@documentation_bp.route("/folders", methods=["POST"])
@token_required
def create_folder():
    """Create a new event folder."""
    data = request.get_json(silent=True) or {}
    folder = DocumentationService.create_folder(data, g.current_user)
    return success_response(data=folder.to_dict(), message="Event folder created successfully.", status_code=201)


@documentation_bp.route("/folders/<int:folder_id>", methods=["GET"])
@token_required
def get_folder(folder_id: int):
    """Get event folder and its document list."""
    data = DocumentationService.get_folder_dict(folder_id, g.current_user)
    return success_response(data=data)


@documentation_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
@token_required
def delete_folder(folder_id: int):
    """Delete event folder and its documents."""
    DocumentationService.delete_folder(folder_id, g.current_user)
    return success_response(message="Event folder and associated files deleted successfully.")


# -----------------------------------------------------------------------------
# Documents Endpoints (Upload, Download, Delete)
# -----------------------------------------------------------------------------
@documentation_bp.route("/folders/<int:folder_id>/documents", methods=["POST"])
@token_required
def upload_document(folder_id: int):
    """Upload a file to an event folder."""
    if "file" not in request.files:
        raise ValidationError("No file provided in multipart upload.", details={"file": ["Required"]})

    file = request.files["file"]
    if not file.filename:
        raise ValidationError("Selected file has an empty filename.")

    content_type = file.content_type or "application/octet-stream"
    doc = DocumentationService.upload_document(
        folder_id=folder_id,
        file_obj=file.stream,
        filename=file.filename,
        content_type=content_type,
        user=g.current_user,
    )
    return success_response(data=doc.to_dict(), message="Document uploaded successfully.", status_code=201)


@documentation_bp.route("/documents/<int:document_id>/download", methods=["GET"])
@token_required
def download_document(document_id: int):
    """Download document file securely."""
    bytes_data, filename, content_type = DocumentationService.get_document_bytes(document_id, g.current_user)
    return send_file(
        io.BytesIO(bytes_data),
        mimetype=content_type,
        as_attachment=True,
        download_name=filename,
    )


@documentation_bp.route("/documents/<int:document_id>", methods=["DELETE"])
@token_required
def delete_document(document_id: int):
    """Delete document from folder and storage."""
    DocumentationService.delete_document(document_id, g.current_user)
    return success_response(message="Document deleted successfully.")


# -----------------------------------------------------------------------------
# AI Activity Reports Endpoints
# -----------------------------------------------------------------------------
@documentation_bp.route("/reports", methods=["GET"])
@token_required
def list_reports():
    """List activity reports and drafts."""
    reports_data = DocumentationService.list_reports_data(g.current_user)
    return success_response(data=reports_data)


@documentation_bp.route("/reports", methods=["POST"])
@token_required
def create_report():
    """Create a new activity report draft."""
    data = request.get_json(silent=True) or {}
    report = DocumentationService.create_report(data, g.current_user)
    return success_response(data=report.to_dict(include_data=True), message="Activity report draft created.", status_code=201)


@documentation_bp.route("/reports/<int:report_id>", methods=["GET"])
@token_required
def get_report(report_id: int):
    """Get activity report details and section data."""
    report_data = DocumentationService.get_report_dict(report_id, g.current_user)
    return success_response(data=report_data)


@documentation_bp.route("/reports/<int:report_id>", methods=["PUT", "PATCH"])
@token_required
def update_report(report_id: int):
    """Update activity report draft content."""
    data = request.get_json(silent=True) or {}
    report = DocumentationService.update_report(report_id, data, g.current_user)
    return success_response(data=report.to_dict(include_data=True), message="Activity report draft saved.")


@documentation_bp.route("/reports/<int:report_id>", methods=["DELETE"])
@token_required
def delete_report(report_id: int):
    """Delete activity report draft."""
    DocumentationService.delete_report(report_id, g.current_user)
    return success_response(message="Activity report deleted successfully.")


@documentation_bp.route("/drive-images", methods=["GET"])
@token_required
def list_drive_images():
    """List all image documents stored in event folders for Drive/workspace selection."""
    images = DocumentationService.list_image_documents(g.current_user)
    return success_response(data=images)


@documentation_bp.route("/reports/analyze-poster", methods=["POST"])
@documentation_bp.route("/reports/<int:report_id>/analyze-poster", methods=["POST"])
@token_required
def analyze_poster(report_id: Optional[int] = None):
    """
    Extract structured context from an uploaded poster image or an existing storage document.
    Accepts multipart file or JSON with base64/document_id.
    """
    image_base64 = None
    mime_type = "image/jpeg"
    filename = "event_poster.jpg"
    provider = None
    model = None

    if "file" in request.files:
        file = request.files["file"]
        if not file.filename:
            raise ValidationError("Attached file has an empty filename.")
        filename = file.filename
        raw_bytes = file.read()
        image_base64, mime_type = optimize_image_bytes(raw_bytes)
        provider = request.form.get("provider")
        model = request.form.get("model")
    else:
        data = request.get_json(silent=True) or {}
        provider = data.get("provider")
        model = data.get("model")

        if data.get("document_id"):
            doc_id = int(data["document_id"])
            bytes_data, orig_name, ctype = DocumentationService.get_document_bytes(doc_id, g.current_user)
            filename = orig_name
            image_base64, mime_type = optimize_image_bytes(bytes_data)
        elif data.get("image_base64"):
            image_base64, mime_type = optimize_base64_image(str(data["image_base64"]))
            filename = data.get("filename") or "poster.jpg"
        else:
            raise ValidationError("Must provide either a file upload, document_id, or image_base64.")

    try:
        extracted, res_provider, res_model = AIService.extract_poster_context(
            image_base64=image_base64,
            image_mime_type=mime_type,
            provider_name=provider,
            model_name=model,
        )
        return success_response(
            data={
                "extracted_data": extracted,
                "filename": filename,
                "mime_type": mime_type,
                "provider": res_provider,
                "model": res_model,
            },
            message="Poster context extracted successfully by AI."
        )
    except AIProviderNotConfiguredError as e:
        return success_response(
            data={"extracted_data": None, "is_configured": False, "notice": str(e)},
            message=str(e),
            status_code=200,
        )


@documentation_bp.route("/reports/<int:report_id>/ai-assist", methods=["POST"])
@documentation_bp.route("/reports/ai-assist", methods=["POST"])
@documentation_bp.route("/ai-assist", methods=["POST"])
@token_required
def ai_assist(report_id: Optional[int] = None):
    """Request AI Copilot assistance for a specific report field, with optional poster visual context."""
    data = request.get_json(silent=True) or {}

    report_context = {}
    if report_id is not None:
        report = DocumentationService.get_report_by_id(report_id, g.current_user)
        report_context = report.get_data().get("general_information", {})
    elif data.get("report_context") and isinstance(data["report_context"], dict):
        report_context = data["report_context"]

    field_key = data.get("field_key") or "general"
    field_label = data.get("field_label") or field_key
    user_instruction = data.get("instruction") or "Draft this section"
    current_content = data.get("current_content") or ""
    action = data.get("action") or "draft"
    requested_provider = data.get("provider")
    requested_model = data.get("model")

    # Optional image context
    image_base64 = data.get("image_base64")
    image_mime_type = data.get("image_mime_type") or "image/jpeg"
    poster_context = data.get("poster_context")

    if data.get("document_id") and not image_base64:
        try:
            doc_id = int(data["document_id"])
            bytes_data, _, _ = DocumentationService.get_document_bytes(doc_id, g.current_user)
            image_base64, image_mime_type = optimize_image_bytes(bytes_data)
        except Exception as e:
            logger.warning("Could not load document %s for AI context: %s", data.get("document_id"), e)
    elif image_base64:
        try:
            image_base64, image_mime_type = optimize_base64_image(str(image_base64))
        except Exception as e:
            logger.warning("Could not optimize user-provided image_base64: %s", e)

    try:
        generated_text, resolved_provider, resolved_model = AIService.assist_field(
            field_key=field_key,
            field_label=field_label,
            user_instruction=user_instruction,
            current_content=current_content,
            report_context=report_context,
            action=action,
            provider_name=requested_provider,
            model_name=requested_model,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
            poster_context=poster_context,
        )
        return success_response(
            data={
                "generated_text": generated_text,
                "field_key": field_key,
                "action": action,
                "provider": resolved_provider,
                "model": resolved_model,
            },
            message="Content generated successfully."
        )
    except AIProviderNotConfiguredError as e:
        return success_response(
            data={
                "generated_text": None,
                "is_configured": False,
                "notice": str(e),
                "field_key": field_key,
                "provider": requested_provider or AIService.get_default_provider_name(),
            },
            message=str(e),
            status_code=200
        )


@documentation_bp.route("/ai/models", methods=["GET"])
@token_required
def list_ai_models():
    """List configured and available AI providers and models."""
    models = AIService.get_available_models()
    return success_response(data=models)


@documentation_bp.route("/reports/<int:report_id>/generate-docx", methods=["POST"])
@token_required
def generate_docx(report_id: int):
    """Generate final DOCX file using the official CUestIC template."""
    output_path, download_filename = DocumentationService.generate_report_docx(report_id, g.current_user)
    return success_response(
        data={
            "report_id": report_id,
            "filename": download_filename,
            "status": "generated",
        },
        message="Report DOCX generated successfully based on official CUestIC template."
    )


@documentation_bp.route("/reports/<int:report_id>/download-docx", methods=["GET"])
@token_required
def download_docx(report_id: int):
    """Download the generated report DOCX."""
    report = DocumentationService.get_report_by_id(report_id, g.current_user)
    if not report.generated_docx_path or not os.path.exists(report.generated_docx_path):
        # Auto-generate if not yet generated
        DocumentationService.generate_report_docx(report_id, g.current_user)

    safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in report.title).strip().replace(" ", "_")
    download_name = f"Activity_Report_{safe_title}.docx"

    return send_file(
        report.generated_docx_path,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=download_name,
    )


@documentation_bp.route("/reports/<int:report_id>/save-to-folder", methods=["POST"])
@token_required
def save_report_to_folder(report_id: int):
    """Optionally save generated report DOCX into an event folder."""
    data = request.get_json(silent=True) or {}
    folder_id = data.get("folder_id")
    if not folder_id:
        raise ValidationError("Target folder_id is required.", details={"folder_id": ["Required"]})

    report = DocumentationService.get_report_by_id(report_id, g.current_user)
    if not report.generated_docx_path or not os.path.exists(report.generated_docx_path):
        DocumentationService.generate_report_docx(report_id, g.current_user)

    safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in report.title).strip().replace(" ", "_")
    filename = f"Activity_Report_{safe_title}.docx"

    with open(report.generated_docx_path, "rb") as f:
        doc = DocumentationService.upload_document(
            folder_id=folder_id,
            file_obj=f,
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            user=g.current_user,
        )

    return success_response(
        data=doc.to_dict(),
        message=f"Report DOCX successfully saved into event folder '{doc.folder.name}'."
    )


# -----------------------------------------------------------------------------
# Attendance Processing & Extraction Endpoints
# -----------------------------------------------------------------------------
@documentation_bp.route("/attendance/process", methods=["POST"])
@token_required
def process_attendance():
    """
    Process attendance sheets (PDF/Image) using OCR and verify signature presence.
    Extracts registration numbers, signature detection status, and class mappings.
    """
    file_bytes = None
    filename = "attendance_sheet"
    existing_records = None

    if "file" in request.files:
        f = request.files["file"]
        filename = f.filename or filename
        file_bytes = f.read()
    else:
        payload = request.get_json(silent=True) or {}
        filename = payload.get("filename", filename)
        b64_str = payload.get("file_base64") or payload.get("image_base64")
        existing_records = payload.get("existing_records")
        if b64_str:
            if ";base64," in b64_str:
                b64_str = b64_str.split(";base64,")[1]
            file_bytes = base64.b64decode(b64_str)

    if not file_bytes:
        raise ValidationError("No attendance file or base64 data provided.", details={"file": ["Required"]})

    # Query Member student directory for mapped registration numbers
    try:
        member_dir = {
            m.registration_number.strip(): m.class_name.strip()
            for m in Member.query.filter(Member.registration_number.isnot(None)).all()
            if m.registration_number and m.class_name
        }
    except Exception:
        member_dir = {}

    result = AttendanceOCRService.process_attendance_file(
        file_bytes=file_bytes,
        filename=filename,
        member_directory=member_dir,
        existing_records=existing_records,
    )

    if not result.get("success"):
        raise ValidationError(result.get("error", "Failed to process attendance sheet."))

    return success_response(
        data=result,
        message=f"Successfully processed {result.get('total_pages', 1)} page(s) with {len(result.get('records', []))} detected records."
    )


@documentation_bp.route("/attendance/verify", methods=["POST"])
@token_required
def verify_attendance_records():
    """
    Recompute attendance summary metrics and class distribution after manual user adjustments.
    """
    payload = request.get_json(silent=True) or {}
    records = payload.get("records")
    if records is None or not isinstance(records, list):
        raise ValidationError("Records list is required.", details={"records": ["Must be a list"]})

    summary = AttendanceOCRService.compute_attendance_summary(records)
    return success_response(
        data={
            "records": records,
            "summary": summary,
        },
        message="Attendance summary recomputed successfully."
    )


@documentation_bp.route("/attendance/class-chart", methods=["POST"])
@token_required
def generate_class_distribution_chart():
    """
    Generate Google Forms style pie chart for class distribution.
    """
    payload = request.get_json(silent=True) or {}
    class_dist = payload.get("class_distribution") or []
    _, chart_b64 = FeedbackAnalysisService.generate_class_distribution_pie_chart(class_dist)
    return success_response(
        data={"chart_base64": chart_b64},
        message="Class distribution chart generated successfully."
    )


# -----------------------------------------------------------------------------
# Feedback Analysis & PO Chart Endpoints
# -----------------------------------------------------------------------------
@documentation_bp.route("/feedback/import", methods=["POST"])
@token_required
def import_feedback_file():
    """
    Import feedback responses from CSV, Excel (.xlsx, .xls), or XML spreadsheet.
    Returns column headers and auto-suggested PO1..PO12 mappings.
    """
    file_bytes = None
    filename = "feedback"

    if "file" in request.files:
        f = request.files["file"]
        filename = f.filename or filename
        file_bytes = f.read()
    else:
        payload = request.get_json(silent=True) or {}
        filename = payload.get("filename", filename)
        b64_str = payload.get("file_base64")
        if b64_str:
            if ";base64," in b64_str:
                b64_str = b64_str.split(";base64,")[1]
            file_bytes = base64.b64decode(b64_str)

    if not file_bytes:
        raise ValidationError("No feedback file provided.", details={"file": ["Required"]})

    parsed = FeedbackAnalysisService.parse_feedback_file(file_bytes, filename)
    if not parsed.get("success"):
        raise ValidationError(parsed.get("error", "Failed to parse feedback file."))

    suggested_mappings = FeedbackAnalysisService.auto_suggest_po_mappings(parsed.get("headers", []))

    return success_response(
        data={
            "filename": filename,
            "headers": parsed.get("headers", []),
            "total_rows": parsed.get("total_rows", 0),
            "rows": parsed.get("rows", []),
            "suggested_mappings": suggested_mappings,
        },
        message=f"Imported feedback file with {parsed.get('total_rows', 0)} response rows."
    )


@documentation_bp.route("/feedback/analyze", methods=["POST"])
@token_required
def analyze_feedback():
    """
    Analyze mapped PO feedback responses, generate Google Forms style pie charts,
    and draft factual interpretation narrative.
    """
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    po_mapping = payload.get("po_column_mapping") or {}

    if not rows:
        raise ValidationError("Rows data is required.", details={"rows": ["Required"]})

    charts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "generated_charts"))
    analysis = FeedbackAnalysisService.analyze_feedback(
        rows=rows,
        po_column_mapping=po_mapping,
        output_dir=charts_dir,
    )

    return success_response(
        data=analysis,
        message=f"Feedback analysis generated for {analysis.get('mapped_pos_count', 0)} Program Outcomes."
    )


# -----------------------------------------------------------------------------
# Simulation Mode Endpoints: Impact & 12 PO Feedback Charts
# -----------------------------------------------------------------------------
@documentation_bp.route("/simulate/impact", methods=["POST"])
@token_required
def simulate_impact_analysis():
    """
    Simulate participant count (200-230), class cohort distribution across the 8 classes,
    Google Forms style Class pie chart, and answers to all 12 Impact Analysis questions.
    """
    payload = request.get_json(silent=True) or {}
    activity_title = payload.get("activity_title") or "Department Club Activity"
    participant_count = payload.get("participant_count")
    seed = payload.get("seed")

    charts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "generated_charts"))
    res = SimulationService.generate_simulated_impact_analysis(
        activity_title=activity_title,
        participant_count=participant_count,
        seed=seed,
        output_dir=charts_dir,
    )
    return success_response(
        data=res,
        message=f"Simulated impact analysis generated for {res['participant_count']} participants across 8 cohorts."
    )


@documentation_bp.route("/simulate/feedback", methods=["POST"])
@token_required
def simulate_feedback_analysis():
    """
    Simulate feedback response distributions for all 12 Programme Outcomes (PO1–PO12)
    or for a specific PO.
    """
    payload = request.get_json(silent=True) or {}
    participant_count = payload.get("participant_count") or 224
    activity_title = payload.get("activity_title") or "Department Club Activity"
    seed = payload.get("seed")
    po_id = payload.get("po_id")

    charts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "generated_charts"))
    if po_id:
        single_res = SimulationService.generate_single_simulated_po(
            po_id=po_id,
            participant_count=int(participant_count),
            seed=seed,
            output_dir=charts_dir,
        )
        return success_response(
            data=single_res,
            message=f"Simulated feedback generated for {po_id}."
        )

    res = SimulationService.generate_simulated_feedback_analysis(
        participant_count=int(participant_count),
        activity_title=activity_title,
        seed=seed,
        output_dir=charts_dir,
    )
    return success_response(
        data=res,
        message=f"Generated 12 simulated Programme Outcome pie charts and distributions for {participant_count} respondents."
    )


