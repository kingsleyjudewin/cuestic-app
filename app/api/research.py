"""
Flask Blueprint for Research Management System API.
Handles Faculty Coordinator and Student Researcher portal interactions,
enforcing RBAC, IDOR protection, and consistent response formatting.
"""
import os
import uuid
from flask import Blueprint, request, g, send_file, current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.user import User
from app.models.research import (
    ResearchAttachment,
    ResearchTask,
    ResearchProject,
)
from app.services.research_service import (
    ResearchService,
    ResearchServiceError,
    ResearchPermissionError,
    ResearchNotFoundError,
)
from app.utils.permissions import token_required, roles_required
from app.utils.errors import success_response, ValidationError, NotFoundError, PermissionDeniedError

research_bp = Blueprint("research", __name__)


def handle_service_error(e: Exception):
    if isinstance(e, ResearchPermissionError):
        raise PermissionDeniedError(str(e))
    elif isinstance(e, ResearchNotFoundError):
        raise NotFoundError(str(e))
    elif isinstance(e, ResearchServiceError):
        raise ValidationError(str(e))
    raise e


# -----------------------------------------------------------------------------
# Profile & First-Login Password Change
# -----------------------------------------------------------------------------

@research_bp.route("/profile", methods=["GET"])
@token_required
def get_current_profile():
    user = g.current_user
    if user.is_faculty_coordinator():
        faculty = ResearchService.get_faculty_profile(user.id)
        return success_response(data={"type": "faculty", "profile": faculty.to_dict()})
    elif user.is_student_researcher():
        student = ResearchService.get_student_profile(user.id)
        return success_response(data={"type": "student", "profile": student.to_dict()})
    else:
        return success_response(data={"type": "user", "profile": user.to_dict()})


@research_bp.route("/faculty/profile", methods=["PUT"])
@token_required
def update_faculty_profile():
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can update this profile.")
    data = request.get_json() or {}
    try:
        updated = ResearchService.update_faculty_profile(user.id, data)
        return success_response(data=updated, message="Faculty profile updated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/auth/first-login-password", methods=["POST"])
@token_required
def first_login_password_change():
    """
    Mandatory password change on first login.
    Resets temporary password and clears must_change_password requirement.
    """
    user = g.current_user
    data = request.get_json() or {}
    curr_pass = (data.get("current_password") or "").strip()
    new_pass = (data.get("new_password") or "").strip()

    if not curr_pass or not new_pass:
        raise ValidationError("Both current password and new password are required.")

    try:
        updated_user = ResearchService.change_first_login_password(
            user_id=user.id,
            current_password=curr_pass,
            new_password=new_pass,
        )
        return success_response(
            data={"user": updated_user},
            message="Password successfully updated. Account setup is complete."
        )
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/auth/change-password", methods=["POST"])
@token_required
def change_password():
    """
    Allow authenticated faculty coordinators and student researchers to change their own password anytime.
    """
    user = g.current_user
    data = request.get_json() or {}
    curr_pass = (data.get("current_password") or "").strip()
    new_pass = (data.get("new_password") or "").strip()

    if not curr_pass or not new_pass:
        raise ValidationError("Both current password and new password are required.")

    try:
        updated_user = ResearchService.change_password(
            user_id=user.id,
            current_password=curr_pass,
            new_password=new_pass,
        )
        return success_response(
            data={"user": updated_user},
            message="Password updated successfully."
        )
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/students/<int:student_id>/password", methods=["POST", "PUT"])
@token_required
def set_student_password(student_id: int):
    """
    Allow faculty coordinator to set or reset a student researcher's password.
    """
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can set student passwords.")

    data = request.get_json() or {}
    new_pass = (data.get("new_password") or data.get("password") or "").strip()
    if not new_pass or len(new_pass) < 6:
        raise ValidationError("New password must be at least 6 characters.")

    try:
        res = ResearchService.set_student_password(
            faculty_user_id=user.id,
            student_id=student_id,
            new_password=new_pass,
        )
        return success_response(data=res, message="Student password updated successfully.")
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Research Teams
# -----------------------------------------------------------------------------

@research_bp.route("/teams", methods=["GET"])
@token_required
def list_teams():
    user = g.current_user
    try:
        if user.is_faculty_coordinator() or user.is_admin():
            teams = ResearchService.get_faculty_teams(user.id)
        elif user.is_student_researcher():
            overview = ResearchService.get_student_dashboard_overview(user.id)
            teams = overview["teams"]
        else:
            teams = []
        return success_response(data=teams)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams", methods=["POST"])
@token_required
def create_team():
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can create research teams.")
    data = request.get_json() or {}
    try:
        team = ResearchService.create_research_team(user.id, data)
        return success_response(data=team, message="Research team created successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams/<int:team_id>", methods=["GET"])
@token_required
def get_team(team_id: int):
    try:
        team = ResearchService.get_team_details(team_id, g.current_user.id)
        return success_response(data=team)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams/<int:team_id>", methods=["PUT"])
@token_required
def update_team(team_id: int):
    data = request.get_json() or {}
    try:
        updated = ResearchService.update_research_team(team_id, g.current_user.id, data)
        return success_response(data=updated, message="Research team updated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams/<int:team_id>", methods=["DELETE"])
@token_required
def delete_team(team_id: int):
    try:
        ResearchService.delete_research_team(team_id, g.current_user.id)
        return success_response(message="Research team deactivated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams/<int:team_id>/students", methods=["POST"])
@token_required
def add_student_to_team(team_id: int):
    data = request.get_json() or {}
    try:
        result = ResearchService.add_student_to_team(
            team_id=team_id,
            user_id=g.current_user.id,
            student_data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=result, message="Student added to research team successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/teams/<int:team_id>/students/<int:student_id>", methods=["DELETE"])
@token_required
def remove_student_from_team(team_id: int, student_id: int):
    try:
        ResearchService.remove_student_from_team(team_id, student_id, g.current_user.id)
        return success_response(message="Student removed from research team successfully.")
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Centralized Student Directory
# -----------------------------------------------------------------------------

@research_bp.route("/directory", methods=["GET"])
@token_required
def get_student_directory():
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can access the student directory.")

    search = request.args.get("search")
    programme = request.args.get("programme")
    semester = request.args.get("semester")

    try:
        directory = ResearchService.get_faculty_student_directory(
            user_id=user.id,
            search=search,
            programme=programme,
            semester=semester,
        )
        return success_response(data=directory)
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Research Projects
# -----------------------------------------------------------------------------

@research_bp.route("/projects", methods=["GET"])
@token_required
def list_projects():
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status")
    try:
        projects = ResearchService.get_projects(g.current_user.id, team_id=team_id, status=status)
        return success_response(data=projects)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/projects", methods=["POST"])
@token_required
def create_project():
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can create projects.")
    data = request.get_json() or {}
    team_id = data.get("team_id")
    if not team_id:
        raise ValidationError("team_id is required to create a project.")

    try:
        project = ResearchService.create_project(
            team_id=team_id,
            user_id=user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=project, message="Project created successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/projects/<int:project_id>", methods=["GET"])
@token_required
def get_project(project_id: int):
    try:
        project = ResearchService.get_project_details(project_id, g.current_user.id)
        return success_response(data=project)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/projects/<int:project_id>", methods=["PUT"])
@token_required
def update_project(project_id: int):
    data = request.get_json() or {}
    try:
        updated = ResearchService.update_project(project_id, g.current_user.id, data)
        return success_response(data=updated, message="Project updated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/projects/<int:project_id>/archive", methods=["POST"])
@token_required
def archive_project(project_id: int):
    try:
        ResearchService.archive_project(project_id, g.current_user.id)
        return success_response(message="Project archived successfully.")
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Milestones & Tasks
# -----------------------------------------------------------------------------

@research_bp.route("/projects/<int:project_id>/milestones", methods=["GET"])
@token_required
def get_project_milestones(project_id: int):
    try:
        milestones = ResearchService.get_project_milestones(project_id, g.current_user.id)
        return success_response(data=milestones)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/projects/<int:project_id>/milestones", methods=["POST"])
@token_required
def create_milestone(project_id: int):
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can create milestones.")
    data = request.get_json() or {}
    try:
        milestone = ResearchService.create_milestone(project_id, user.id, data)
        return success_response(data=milestone, message="Milestone created successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/milestones/<int:milestone_id>/tasks", methods=["GET"])
@token_required
def get_milestone_tasks(milestone_id: int):
    try:
        tasks = ResearchService.get_milestone_tasks(milestone_id, g.current_user.id)
        return success_response(data=tasks)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/milestones/<int:milestone_id>/tasks", methods=["POST"])
@token_required
def create_task(milestone_id: int):
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can create tasks.")
    data = request.get_json() or {}
    try:
        task = ResearchService.create_task(
            milestone_id=milestone_id,
            user_id=user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=task, message="Task created successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/tasks/<int:task_id>/assignees", methods=["POST"])
@token_required
def assign_task_students(task_id: int):
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can assign students.")
    data = request.get_json() or {}
    student_ids = data.get("student_ids", [])
    try:
        task = ResearchService.assign_task_students(
            task_id=task_id,
            user_id=user.id,
            student_ids=student_ids,
            app=current_app._get_current_object(),
        )
        return success_response(data=task, message="Task assignees updated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@token_required
def update_task_status(task_id: int):
    data = request.get_json() or {}
    status = data.get("status")
    if not status:
        raise ValidationError("status is required.")

    pct = data.get("progress_percentage")
    notes = data.get("notes")
    try:
        task = ResearchService.update_task_status(
            task_id=task_id,
            user_id=g.current_user.id,
            status=status,
            progress_percentage=pct,
            notes=notes,
            app=current_app._get_current_object(),
        )
        return success_response(data=task, message="Task status updated successfully.")
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Progress Submissions & Continuous Two-Way Feedback
# -----------------------------------------------------------------------------

@research_bp.route("/tasks/<int:task_id>/submissions", methods=["POST"])
@token_required
def submit_progress(task_id: int):
    """
    Student submits measurable progress update with metrics, comments, attachments.
    """
    user = g.current_user
    if not user.is_student_researcher():
        raise PermissionDeniedError("Only assigned student researchers can submit progress.")
    data = request.get_json() or {}
    try:
        submission = ResearchService.submit_progress(
            task_id=task_id,
            user_id=user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=submission, message="Progress submitted for review.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/tasks/<int:task_id>/thread", methods=["GET"])
@token_required
def get_feedback_thread(task_id: int):
    try:
        thread = ResearchService.get_task_feedback_thread(task_id, g.current_user.id)
        return success_response(data=thread)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/tasks/<int:task_id>/messages", methods=["POST"])
@token_required
def add_feedback_message(task_id: int):
    """
    Add continuous feedback / response message (faculty or student).
    """
    data = request.get_json() or {}
    try:
        msg = ResearchService.add_feedback_message(
            task_id=task_id,
            user_id=g.current_user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=msg, message="Message sent.", status_code=201)
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# File Attachments Upload & Download
# -----------------------------------------------------------------------------

@research_bp.route("/attachments/upload", methods=["POST"])
@token_required
def upload_research_attachment():
    """
    Multipart upload for research deliverables (papers, datasets, reports).
    """
    if "file" not in request.files:
        raise ValidationError("No file provided in multipart upload.", details={"file": ["Required"]})

    file = request.files["file"]
    if not file or not file.filename:
        raise ValidationError("Selected file is empty.", details={"file": ["Invalid"]})

    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"

    upload_folder = os.path.join(current_app.root_path, "..", "uploads", "research")
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, unique_name)
    file.save(file_path)

    size = os.path.getsize(file_path)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    return success_response(
        data={
            "file_name": filename,
            "storage_path": f"/uploads/research/{unique_name}",
            "file_size": size,
            "file_type": ext or "document",
            "file_url": f"/api/v1/research/attachments/file/{unique_name}",
        },
        message="Attachment uploaded successfully.",
        status_code=201,
    )


@research_bp.route("/attachments/file/<filename>", methods=["GET"])
def download_attachment_by_filename(filename: str):
    clean = secure_filename(filename)
    upload_folder = os.path.join(current_app.root_path, "..", "uploads", "research")
    path = os.path.join(upload_folder, clean)
    if not os.path.exists(path):
        raise NotFoundError("Attachment file not found.")
    return send_file(path)


# -----------------------------------------------------------------------------
# Meeting Scheduler
# -----------------------------------------------------------------------------

@research_bp.route("/meetings", methods=["GET"])
@token_required
def list_meetings():
    try:
        meetings = ResearchService.get_meetings(g.current_user.id)
        return success_response(data=meetings)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/meetings", methods=["POST"])
@token_required
def schedule_meeting():
    user = g.current_user
    if not (user.is_faculty_coordinator() or user.is_admin()):
        raise PermissionDeniedError("Only faculty coordinators can schedule meetings.")
    data = request.get_json() or {}
    try:
        meeting = ResearchService.schedule_meeting(
            user_id=user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=meeting, message="Meeting scheduled successfully.", status_code=201)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/meetings/<int:meeting_id>", methods=["PUT"])
@token_required
def update_meeting(meeting_id: int):
    data = request.get_json() or {}
    try:
        meeting = ResearchService.update_meeting(
            meeting_id=meeting_id,
            user_id=g.current_user.id,
            data=data,
            app=current_app._get_current_object(),
        )
        return success_response(data=meeting, message="Meeting updated successfully.")
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/meetings/<int:meeting_id>/attendance", methods=["POST"])
@token_required
def record_meeting_attendance(meeting_id: int):
    data = request.get_json() or {}
    attendance_records = data.get("attendance", [])
    notes = data.get("notes")
    try:
        result = ResearchService.record_meeting_attendance(
            meeting_id=meeting_id,
            user_id=g.current_user.id,
            attendance_records=attendance_records,
            notes=notes,
        )
        return success_response(data=result, message="Attendance recorded successfully.")
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# Student Portal Dashboard Overview
# -----------------------------------------------------------------------------

@research_bp.route("/student/overview", methods=["GET"])
@token_required
def student_overview():
    user = g.current_user
    if not user.is_student_researcher():
        raise PermissionDeniedError("Only student researchers can access this endpoint.")
    try:
        data = ResearchService.get_student_dashboard_overview(user.id)
        return success_response(data=data)
    except Exception as e:
        handle_service_error(e)


# -----------------------------------------------------------------------------
# In-App Notifications
# -----------------------------------------------------------------------------

@research_bp.route("/notifications", methods=["GET"])
@token_required
def get_notifications():
    try:
        notifs = ResearchService.get_notifications(g.current_user.id)
        return success_response(data=notifs)
    except Exception as e:
        handle_service_error(e)


@research_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@token_required
def mark_notification_read(notif_id: int):
    success = ResearchService.mark_notification_read(notif_id, g.current_user.id)
    return success_response(data={"read": success})
