"""
Comprehensive Service Layer for Research Management System.
Enforces strict faculty isolation and student authorization,
data validation, audit logging, and automated notification triggers.
"""
import re
import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.models.user import User
from app.models.member import Member
from app.models.research import (
    FacultyProfile,
    ResearchStudentProfile,
    ResearchTeam,
    ResearchTeamMember,
    ResearchProject,
    ResearchProjectMember,
    ResearchMilestone,
    ResearchMilestoneAssignee,
    ResearchTask,
    ResearchTaskAssignee,
    ResearchProgressSubmission,
    ResearchFeedbackThread,
    ResearchFeedbackMessage,
    ResearchAttachment,
    ResearchMeeting,
    ResearchMeetingParticipant,
    ResearchNotification,
)
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func
from app.services.research_cache import research_cache
from app.services.research_email_service import ResearchEmailService


class ResearchServiceError(Exception):
    """Base exception for research service business rule violations."""
    pass


class ResearchPermissionError(ResearchServiceError):
    """Raised when access is unauthorized or violates ownership boundaries."""
    pass


class ResearchNotFoundError(ResearchServiceError):
    """Raised when an entity is not found."""
    pass


class ResearchService:
    """Service providing all research management operations."""

    # -------------------------------------------------------------------------
    # Authentication & Profile Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def get_faculty_id(user_id: int) -> int:
        cached_id = research_cache.get(f"faculty_id:user:{user_id}")
        if cached_id is not None:
            return cached_id
        faculty = (
            FacultyProfile.query.filter_by(user_id=user_id)
            .with_entities(FacultyProfile.id)
            .first()
        )
        if not faculty:
            raise ResearchNotFoundError("Faculty coordinator profile not found for this user.")
        fid = faculty.id
        research_cache.set(f"faculty_id:user:{user_id}", fid, ttl=86400)
        return fid

    @staticmethod
    def get_student_id(user_id: int) -> int:
        cached_id = research_cache.get(f"student_id:user:{user_id}")
        if cached_id is not None:
            return cached_id
        student = (
            ResearchStudentProfile.query.filter_by(user_id=user_id)
            .with_entities(ResearchStudentProfile.id)
            .first()
        )
        if not student:
            raise ResearchNotFoundError("Student researcher profile not found for this user.")
        sid = student.id
        research_cache.set(f"student_id:user:{user_id}", sid, ttl=86400)
        return sid

    @staticmethod
    def get_faculty_profile(user_id: int) -> FacultyProfile:
        faculty = (
            FacultyProfile.query.filter_by(user_id=user_id)
            .options(joinedload(FacultyProfile.user))
            .first()
        )
        if not faculty:
            raise ResearchNotFoundError("Faculty coordinator profile not found for this user.")
        research_cache.set(f"faculty_id:user:{user_id}", faculty.id, ttl=86400)
        return faculty

    @staticmethod
    def get_student_profile(user_id: int) -> ResearchStudentProfile:
        student = (
            ResearchStudentProfile.query.filter_by(user_id=user_id)
            .options(joinedload(ResearchStudentProfile.user))
            .first()
        )
        if not student:
            raise ResearchNotFoundError("Student researcher profile not found for this user.")
        research_cache.set(f"student_id:user:{user_id}", student.id, ttl=86400)
        return student

    @classmethod
    def change_first_login_password(
        cls,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> Dict[str, Any]:
        """
        Forces password change on first login or profile update.
        """
        return cls.change_password(user_id=user_id, current_password=current_password, new_password=new_password)

    @classmethod
    def change_password(
        cls,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> Dict[str, Any]:
        """
        Allows any research user (faculty coordinator or student researcher)
        to change their own password at any time.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ResearchNotFoundError("User not found.")

        if not user.check_password(current_password):
            raise ResearchServiceError("The current password provided is incorrect.")

        if len(new_password) < 6:
            raise ResearchServiceError("New password must be at least 6 characters long.")

        if current_password == new_password:
            raise ResearchServiceError("New password must be different from current password.")

        user.set_password(new_password)
        user.credential_setup_status = "completed"

        if user.faculty_profile:
            user.faculty_profile.must_change_password = False
        if user.research_student_profile:
            user.research_student_profile.must_change_password = False

        db.session.commit()
        return user.to_dict()

    @classmethod
    def set_student_password(
        cls,
        faculty_user_id: int,
        student_id: int,
        new_password: str,
    ) -> Dict[str, Any]:
        """
        Allows a faculty coordinator to set/reset a student's password.
        Faculty must coordinate at least one team the student belongs to, unless admin.
        """
        faculty = cls.get_faculty_profile(faculty_user_id)
        student_profile = db.session.get(ResearchStudentProfile, student_id)
        if not student_profile:
            raise ResearchNotFoundError("Student researcher not found.")

        user = faculty.user
        if not user.is_admin():
            faculty_team_ids = [t.id for t in faculty.teams.filter_by(is_active=True).all()]
            is_member = ResearchTeamMember.query.filter(
                ResearchTeamMember.team_id.in_(faculty_team_ids),
                ResearchTeamMember.student_id == student_profile.id,
                ResearchTeamMember.is_active == True,
            ).first()
            if not is_member:
                raise ResearchPermissionError("You do not have permission to manage this student's credentials.")

        student_user = student_profile.user
        if not student_user:
            raise ResearchNotFoundError("User account for student not found.")

        if len(new_password) < 6:
            raise ResearchServiceError("Password must be at least 6 characters long.")

        student_user.set_password(new_password)
        student_user.credential_setup_status = "completed"
        student_profile.must_change_password = False
        db.session.commit()

        return {
            "student_id": student_profile.id,
            "username": student_user.username,
            "full_name": student_profile.full_name,
            "new_password": new_password,
        }

    @classmethod
    def update_faculty_profile(cls, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update faculty member profile information.
        """
        faculty = cls.get_faculty_profile(user_id)
        if "specialization" in data:
            faculty.specialization = (data["specialization"] or "").strip()
        if "research_interests" in data:
            faculty.research_interests = (data["research_interests"] or "").strip()
        if "bio" in data:
            faculty.bio = (data["bio"] or "").strip()
        if "phone_number" in data:
            faculty.phone_number = (data["phone_number"] or "").strip()
        if "email" in data:
            email = (data["email"] or "").strip().lower()
            if email:
                existing = User.query.filter(User.email == email, User.id != user_id).first()
                if existing:
                    raise ResearchServiceError("This email address is already in use.")
                faculty.user.email = email

        db.session.commit()
        return faculty.to_dict()

    # -------------------------------------------------------------------------
    # Research Teams
    # -------------------------------------------------------------------------

    @classmethod
    def create_research_team(cls, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        name = (data.get("name") or "").strip()
        domain = (data.get("domain") or "").strip()
        if not name:
            raise ResearchServiceError("Research team name is required.")
        if not domain:
            raise ResearchServiceError("Research domain is required.")

        team = ResearchTeam(
            faculty_id=faculty.id,
            name=name,
            domain=domain,
            description=(data.get("description") or "").strip(),
            objectives=(data.get("objectives") or "").strip(),
            tags_json=data.get("tags_json"),
            is_active=True,
        )
        db.session.add(team)
        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        return team.to_dict(include_members=True, include_projects=True)

    @classmethod
    def get_faculty_teams(cls, user_id: int) -> List[Dict[str, Any]]:
        faculty_id = cls.get_faculty_id(user_id)
        cache_key = f"teams:faculty:{faculty_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        faculty = cls.get_faculty_profile(user_id)
        teams = (
            ResearchTeam.query.filter_by(faculty_id=faculty.id, is_active=True)
            .options(joinedload(ResearchTeam.faculty))
            .order_by(ResearchTeam.created_at.desc())
            .all()
        )
        if not teams:
            research_cache.set(cache_key, [], tags=[f"faculty:{faculty.id}", "global:teams"])
            return []

        team_ids = [t.id for t in teams]

        # Bulk load active members with student and user
        members = (
            ResearchTeamMember.query.filter(
                ResearchTeamMember.team_id.in_(team_ids),
                ResearchTeamMember.is_active == True,
            )
            .options(
                joinedload(ResearchTeamMember.student).joinedload(ResearchStudentProfile.user)
            )
            .all()
        )
        team_members_map: Dict[int, List[Dict[str, Any]]] = {tid: [] for tid in team_ids}
        for m in members:
            team_members_map[m.team_id].append(m.to_dict())

        # Bulk load active projects
        projects = (
            ResearchProject.query.filter(
                ResearchProject.team_id.in_(team_ids),
                ResearchProject.is_archived == False,
            )
            .options(joinedload(ResearchProject.team), joinedload(ResearchProject.faculty))
            .all()
        )
        team_projects_map: Dict[int, List[Dict[str, Any]]] = {tid: [] for tid in team_ids}
        for p in projects:
            team_projects_map[p.team_id].append(p.to_dict(include_milestones=False, include_members=False))

        result = []
        for t in teams:
            td = t.to_dict(
                include_members=False,
                include_projects=False,
                member_count=len(team_members_map[t.id]),
                project_count=len(team_projects_map[t.id]),
            )
            td["members"] = team_members_map[t.id]
            td["projects"] = team_projects_map[t.id]
            result.append(td)

        research_cache.set(cache_key, result, tags=[f"faculty:{faculty.id}", "global:teams"])
        return result

    @classmethod
    def get_team_details(cls, team_id: int, user_id: int) -> Dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ResearchPermissionError("Unauthorized.")

        team = db.session.get(ResearchTeam, team_id)
        if not team:
            raise ResearchNotFoundError("Research team not found.")

        # Check permission: Faculty owner OR enrolled Student Researcher OR Admin
        if user.is_faculty_coordinator():
            faculty = cls.get_faculty_profile(user_id)
            if team.faculty_id != faculty.id:
                raise ResearchPermissionError("You do not have permission to access this research team.")
        elif user.is_student_researcher():
            student = cls.get_student_profile(user_id)
            membership = ResearchTeamMember.query.filter_by(
                team_id=team_id, student_id=student.id, is_active=True
            ).first()
            if not membership:
                raise ResearchPermissionError("You are not an active member of this research team.")
        elif not user.is_admin():
            raise ResearchPermissionError("Access denied.")

        return team.to_dict(include_members=True, include_projects=True)

    @classmethod
    def update_research_team(cls, team_id: int, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        team = db.session.get(ResearchTeam, team_id)
        if not team or team.faculty_id != faculty.id:
            raise ResearchPermissionError("Team not found or not owned by you.")

        if "name" in data and data["name"]:
            team.name = data["name"].strip()
        if "domain" in data and data["domain"]:
            team.domain = data["domain"].strip()
        if "description" in data:
            team.description = (data["description"] or "").strip()
        if "objectives" in data:
            team.objectives = (data["objectives"] or "").strip()
        if "tags_json" in data:
            team.tags_json = data["tags_json"]

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        return team.to_dict(include_members=True, include_projects=True)

    @classmethod
    def delete_research_team(cls, team_id: int, user_id: int) -> bool:
        faculty = cls.get_faculty_profile(user_id)
        team = db.session.get(ResearchTeam, team_id)
        if not team or team.faculty_id != faculty.id:
            raise ResearchPermissionError("Team not found or not owned by you.")

        team.is_active = False
        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        return True

    # -------------------------------------------------------------------------
    # Adding & Removing Students to Teams
    # -------------------------------------------------------------------------

    @classmethod
    def add_student_to_team(
        cls,
        team_id: int,
        user_id: int,
        student_data: Dict[str, Any],
        app=None,
    ) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        team = db.session.get(ResearchTeam, team_id)
        if not team or team.faculty_id != faculty.id:
            raise ResearchPermissionError("Research team not found or not owned by you.")

        reg_num = (student_data.get("registration_number") or "").strip().upper()
        email = (student_data.get("email") or "").strip().lower()
        full_name = (student_data.get("full_name") or "").strip()

        if not reg_num or not full_name:
            raise ResearchServiceError("Registration number and full student name are required.")
        if not email or "@" not in email:
            raise ResearchServiceError("A valid university email address is required.")

        # Check if research student profile already exists
        student_profile = ResearchStudentProfile.query.filter(
            (ResearchStudentProfile.registration_number == reg_num) |
            (ResearchStudentProfile.email == email)
        ).first()

        custom_password = (student_data.get("password") or "").strip()
        if custom_password:
            if len(custom_password) < 6:
                raise ResearchServiceError("Student password must be at least 6 characters long.")
            temp_password = custom_password
        else:
            temp_password = f"ResPass2026!{reg_num[-4:] if len(reg_num) >= 4 else '9999'}"

        if not student_profile:
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', full_name.split()[0].lower())
            base_username = f"res_{clean_name}_{reg_num.lower()}"
            username = base_username
            suffix = 1
            while User.query.filter_by(username=username).first():
                suffix += 1
                username = f"{base_username}_{suffix}"

            linked_member = Member.query.filter(
                (Member.registration_number == reg_num) | (Member.email == email)
            ).first()

            user = User(
                username=username,
                email=email,
                role=User.ROLE_STUDENT_RESEARCHER,
                is_active=True,
                credential_setup_status="completed",
            )
            user.set_password(temp_password)
            db.session.add(user)
            db.session.flush()

            student_profile = ResearchStudentProfile(
                user_id=user.id,
                member_id=linked_member.id if linked_member else None,
                full_name=full_name,
                registration_number=reg_num,
                email=email,
                department=student_data.get("department", "Electronics and Communication Engineering"),
                programme=student_data.get("programme", "B.Tech ECE"),
                semester=student_data.get("semester", "Semester 5"),
                phone_number=student_data.get("phone_number"),
                must_change_password=False,
                is_active=True,
            )
            db.session.add(student_profile)
            db.session.flush()

            if app:
                ResearchEmailService.notify_student_account_created(
                    app=app,
                    student=student_profile,
                    temp_password=temp_password,
                )
        elif custom_password:
            # Faculty assigned a new password for the existing student account
            if student_profile.user:
                student_profile.user.set_password(custom_password)
                student_profile.user.credential_setup_status = "completed"
            student_profile.must_change_password = False

        # Check existing team membership
        membership = ResearchTeamMember.query.filter_by(
            team_id=team.id, student_id=student_profile.id
        ).first()

        if membership:
            if not membership.is_active:
                membership.is_active = True
                db.session.commit()
            return {
                "student": student_profile.to_dict(),
                "team_id": team.id,
                "status": "already_member",
                "username": student_profile.user.username if student_profile.user else None,
                "password": temp_password,
                "temporary_password": temp_password,
            }

        new_membership = ResearchTeamMember(
            team_id=team.id,
            student_id=student_profile.id,
            is_active=True,
        )
        db.session.add(new_membership)
        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_student(student_profile.id)

        if app:
            ResearchEmailService.notify_student_added_to_team(
                app=app,
                student=student_profile,
                team=team,
                faculty=faculty,
            )

        res = {
            "student": student_profile.to_dict(),
            "team_id": team.id,
            "status": "added",
            "username": student_profile.user.username if student_profile.user else None,
            "password": temp_password,
            "temporary_password": temp_password,
        }
        return res

    @classmethod
    def remove_student_from_team(cls, team_id: int, student_id: int, user_id: int) -> bool:
        faculty = cls.get_faculty_profile(user_id)
        team = db.session.get(ResearchTeam, team_id)
        if not team or team.faculty_id != faculty.id:
            raise ResearchPermissionError("Team not found or not owned by you.")

        membership = ResearchTeamMember.query.filter_by(
            team_id=team_id, student_id=student_id
        ).first()
        if not membership:
            raise ResearchNotFoundError("Student is not in this team.")

        db.session.delete(membership)
        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_student(student_id)
        return True

    # -------------------------------------------------------------------------
    # Centralized Student Directory (Consolidated & Deduplicated)
    # -------------------------------------------------------------------------

    @classmethod
    def get_faculty_student_directory(
        cls,
        user_id: int,
        search: Optional[str] = None,
        programme: Optional[str] = None,
        semester: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        faculty_id = cls.get_faculty_id(user_id)
        cache_key = f"directory:faculty:{faculty_id}:{search or ''}:{programme or ''}:{semester or ''}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        faculty = cls.get_faculty_profile(user_id)

        teams = ResearchTeam.query.filter_by(faculty_id=faculty.id, is_active=True).all()
        team_ids = [t.id for t in teams]

        if not team_ids:
            research_cache.set(cache_key, [], tags=[f"faculty:{faculty.id}", "global:directory"])
            return []

        memberships = (
            ResearchTeamMember.query.filter(
                ResearchTeamMember.team_id.in_(team_ids),
                ResearchTeamMember.is_active == True,
            )
            .options(
                joinedload(ResearchTeamMember.student).joinedload(ResearchStudentProfile.user),
                joinedload(ResearchTeamMember.team),
            )
            .all()
        )

        student_dict: Dict[int, Dict[str, Any]] = {}
        for m in memberships:
            st = m.student
            if not st or not st.is_active:
                continue

            if st.id not in student_dict:
                student_dict[st.id] = {
                    "id": st.id,
                    "user_id": st.user_id,
                    "full_name": st.full_name,
                    "registration_number": st.registration_number,
                    "email": st.email,
                    "department": st.department,
                    "programme": st.programme,
                    "semester": st.semester,
                    "phone_number": st.phone_number,
                    "profile_image_url": st.profile_image_url,
                    "teams": [],
                    "projects": [],
                    "tasks_count": 0,
                    "completed_tasks_count": 0,
                    "created_at": st.created_at.isoformat() if st.created_at else None,
                }

            student_dict[st.id]["teams"].append({
                "id": m.team.id,
                "name": m.team.name,
                "domain": m.team.domain,
            })

        faculty_project_ids = [
            p.id for p in ResearchProject.query.filter_by(faculty_id=faculty.id, is_archived=False).all()
        ]

        if faculty_project_ids and student_dict:
            student_ids = list(student_dict.keys())
            proj_members = (
                ResearchProjectMember.query.filter(
                    ResearchProjectMember.project_id.in_(faculty_project_ids),
                    ResearchProjectMember.student_id.in_(student_ids),
                )
                .options(joinedload(ResearchProjectMember.project))
                .all()
            )

            for pm in proj_members:
                if pm.student_id in student_dict:
                    student_dict[pm.student_id]["projects"].append({
                        "id": pm.project.id,
                        "title": pm.project.title,
                        "role": pm.role,
                        "status": pm.project.status,
                    })

            # Single bulk aggregate query for tasks counts per student
            task_counts = (
                db.session.query(
                    ResearchTaskAssignee.student_id,
                    func.count(ResearchTask.id).label("total"),
                    func.count(func.nullif(ResearchTask.status != "approved", True)).label("completed"),
                )
                .join(ResearchTask, ResearchTaskAssignee.task_id == ResearchTask.id)
                .filter(
                    ResearchTaskAssignee.student_id.in_(student_ids),
                    ResearchTask.project_id.in_(faculty_project_ids),
                )
                .group_by(ResearchTaskAssignee.student_id)
                .all()
            )
            for sid, total, completed in task_counts:
                if sid in student_dict:
                    student_dict[sid]["tasks_count"] = total
                    student_dict[sid]["completed_tasks_count"] = completed

        results = list(student_dict.values())

        if search:
            s = search.lower().strip()
            results = [
                r for r in results
                if s in r["full_name"].lower() or s in r["registration_number"].lower() or s in r["email"].lower()
            ]
        if programme:
            results = [r for r in results if r["programme"] == programme]
        if semester:
            results = [r for r in results if r["semester"] == semester]

        results.sort(key=lambda x: x["full_name"])
        research_cache.set(cache_key, results, tags=[f"faculty:{faculty.id}", "global:directory"])
        return results

    # -------------------------------------------------------------------------
    # Research Projects
    # -------------------------------------------------------------------------

    @classmethod
    def create_project(cls, team_id: int, user_id: int, data: Dict[str, Any], app=None) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        team = db.session.get(ResearchTeam, team_id)
        if not team or team.faculty_id != faculty.id:
            raise ResearchPermissionError("Team not found or not owned by you.")

        title = (data.get("title") or "").strip()
        if not title:
            raise ResearchServiceError("Project title is required.")

        start_date = None
        if data.get("start_date"):
            try:
                start_date = datetime.fromisoformat(data["start_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        completion_date = None
        if data.get("expected_completion_date"):
            try:
                completion_date = datetime.fromisoformat(data["expected_completion_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        project = ResearchProject(
            team_id=team.id,
            faculty_id=faculty.id,
            title=title,
            research_problem=(data.get("research_problem") or "").strip(),
            objectives=(data.get("objectives") or "").strip(),
            description=(data.get("description") or "").strip(),
            start_date=start_date,
            expected_completion_date=completion_date,
            status=data.get("status", "in_progress"),
            is_archived=False,
        )
        db.session.add(project)
        db.session.flush()

        student_ids = data.get("assigned_student_ids") or []
        for sid in student_ids:
            st = db.session.get(ResearchStudentProfile, sid)
            if st:
                pm = ResearchProjectMember(project_id=project.id, student_id=st.id)
                db.session.add(pm)
                if app:
                    ResearchEmailService.notify_student_assigned_to_project(
                        app=app,
                        student=st,
                        project=project,
                        faculty=faculty,
                    )

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        for sid in student_ids:
            research_cache.invalidate_student(sid)
        return project.to_dict(include_milestones=True, include_members=True)

    @classmethod
    def get_projects(
        cls,
        user_id: int,
        team_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        user = db.session.get(User, user_id)
        if not user:
            raise ResearchPermissionError("Unauthorized.")

        is_faculty = user.is_faculty_coordinator()
        is_student = user.is_student_researcher()
        role_type = "faculty" if is_faculty else ("student" if is_student else "admin")
        cache_key = f"projects:{role_type}:{user_id}:{team_id or ''}:{status or ''}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        eager_opts = [
            joinedload(ResearchProject.team),
            joinedload(ResearchProject.faculty),
            selectinload(ResearchProject.milestones).selectinload(ResearchMilestone.tasks).selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student),
        ]

        if is_faculty:
            faculty_id = cls.get_faculty_id(user_id)
            query = ResearchProject.query.filter_by(faculty_id=faculty_id, is_archived=False)
            if team_id:
                query = query.filter_by(team_id=team_id)
            if status:
                query = query.filter_by(status=status)
            projects = query.options(*eager_opts).order_by(ResearchProject.created_at.desc()).all()
            res = [p.to_dict(include_milestones=True, include_members=True) for p in projects]
            research_cache.set(cache_key, res, tags=[f"faculty:{faculty_id}", "global:projects"])
            return res

        elif is_student:
            student = cls.get_student_profile(user_id)
            proj_memberships = ResearchProjectMember.query.filter_by(student_id=student.id).all()
            project_ids = [pm.project_id for pm in proj_memberships]
            if not project_ids:
                research_cache.set(cache_key, [], tags=[f"student:{student.id}", "global:projects"])
                return []
            projects = (
                ResearchProject.query.filter(
                    ResearchProject.id.in_(project_ids),
                    ResearchProject.is_archived == False,
                )
                .options(*eager_opts)
                .order_by(ResearchProject.created_at.desc())
                .all()
            )
            res = [p.to_dict(include_milestones=True, include_members=True) for p in projects]
            research_cache.set(cache_key, res, tags=[f"student:{student.id}", "global:projects"])
            return res

        return []

    @classmethod
    def get_project_details(cls, project_id: int, user_id: int) -> Dict[str, Any]:
        user = db.session.get(User, user_id)
        project = (
            ResearchProject.query.filter_by(id=project_id)
            .options(
                joinedload(ResearchProject.team),
                joinedload(ResearchProject.faculty),
                selectinload(ResearchProject.milestones).selectinload(ResearchMilestone.tasks).selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student),
            )
            .first()
        )
        if not project:
            raise ResearchNotFoundError("Research project not found.")

        if user.is_faculty_coordinator():
            faculty = cls.get_faculty_profile(user_id)
            if project.faculty_id != faculty.id:
                raise ResearchPermissionError("Access denied.")
        elif user.is_student_researcher():
            student = cls.get_student_profile(user_id)
            pm = ResearchProjectMember.query.filter_by(project_id=project.id, student_id=student.id).first()
            if not pm:
                raise ResearchPermissionError("You are not assigned to this project.")
        elif not user.is_admin():
            raise ResearchPermissionError("Access denied.")

        return project.to_dict(include_milestones=True, include_members=True)

    @classmethod
    def update_project(cls, project_id: int, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        project = db.session.get(ResearchProject, project_id)
        if not project or project.faculty_id != faculty.id:
            raise ResearchPermissionError("Project not found or not owned by you.")

        if "title" in data and data["title"]:
            project.title = data["title"].strip()
        if "research_problem" in data:
            project.research_problem = (data["research_problem"] or "").strip()
        if "objectives" in data:
            project.objectives = (data["objectives"] or "").strip()
        if "description" in data:
            project.description = (data["description"] or "").strip()
        if "status" in data:
            project.status = data["status"]
        if "is_archived" in data:
            project.is_archived = bool(data["is_archived"])

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_project(project.id)
        return project.to_dict(include_milestones=True, include_members=True)

    @classmethod
    def archive_project(cls, project_id: int, user_id: int) -> bool:
        faculty = cls.get_faculty_profile(user_id)
        project = db.session.get(ResearchProject, project_id)
        if not project or project.faculty_id != faculty.id:
            raise ResearchPermissionError("Project not found or not owned by you.")

        project.is_archived = True
        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_project(project.id)
        return True

    # -------------------------------------------------------------------------
    # Milestones & Tasks Management
    # -------------------------------------------------------------------------

    @classmethod
    def create_milestone(cls, project_id: int, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        project = db.session.get(ResearchProject, project_id)
        if not project or project.faculty_id != faculty.id:
            raise ResearchPermissionError("Project not found or not owned by you.")

        title = (data.get("title") or "").strip()
        if not title:
            raise ResearchServiceError("Milestone title is required.")

        start_date = None
        if data.get("start_date"):
            try:
                start_date = datetime.fromisoformat(data["start_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        due_date = None
        if data.get("due_date"):
            try:
                due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        milestone = ResearchMilestone(
            project_id=project.id,
            title=title,
            description=(data.get("description") or "").strip(),
            target_criteria=(data.get("target_criteria") or "").strip(),
            start_date=start_date,
            due_date=due_date,
            priority=data.get("priority", "medium"),
            status=data.get("status", "in_progress"),
            completion_percentage=0,
        )
        db.session.add(milestone)
        db.session.flush()

        assigned_students = data.get("assigned_student_ids") or []
        for sid in assigned_students:
            db.session.add(ResearchMilestoneAssignee(milestone_id=milestone.id, student_id=sid))

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_project(project.id)
        for sid in assigned_students:
            research_cache.invalidate_student(sid)
        return milestone.to_dict(include_tasks=True)

    @classmethod
    def create_task(cls, milestone_id: int, user_id: int, data: Dict[str, Any], app=None) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        milestone = db.session.get(ResearchMilestone, milestone_id)
        if not milestone or milestone.project.faculty_id != faculty.id:
            raise ResearchPermissionError("Milestone not found or not owned by you.")

        title = (data.get("title") or "").strip()
        if not title:
            raise ResearchServiceError("Task title is required.")

        due_date = None
        if data.get("due_date"):
            try:
                due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        task = ResearchTask(
            milestone_id=milestone.id,
            project_id=milestone.project_id,
            title=title,
            instructions=(data.get("instructions") or "").strip(),
            completion_criteria=(data.get("completion_criteria") or "").strip(),
            priority=data.get("priority", "medium"),
            due_date=due_date,
            status=data.get("status", "not_started"),
            progress_percentage=0,
            created_by=user_id,
        )
        db.session.add(task)
        db.session.flush()

        assigned_students = data.get("assigned_student_ids") or []
        for sid in assigned_students:
            st = db.session.get(ResearchStudentProfile, sid)
            if st:
                db.session.add(ResearchTaskAssignee(task_id=task.id, student_id=st.id))
                if app:
                    ResearchEmailService.notify_task_assigned(
                        app=app,
                        student=st,
                        task=task,
                        project=milestone.project,
                    )

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        research_cache.invalidate_project(milestone.project_id)
        research_cache.invalidate_task(task.id)
        for sid in assigned_students:
            research_cache.invalidate_student(sid)
        return task.to_dict()

    @classmethod
    def assign_task_students(
        cls,
        task_id: int,
        user_id: int,
        student_ids: List[int],
        app=None,
    ) -> Dict[str, Any]:
        """
        Bulk assign or reassign students to a specific task.
        """
        user = db.session.get(User, user_id)
        task = db.session.get(ResearchTask, task_id)
        if not task:
            raise ResearchNotFoundError("Task not found.")

        faculty = cls.get_faculty_profile(user_id)
        if task.milestone.project.faculty_id != faculty.id:
            raise ResearchPermissionError("Unauthorized to modify task assignees.")

        existing_assignees = ResearchTaskAssignee.query.filter_by(task_id=task.id).all()
        existing_sids = {a.student_id for a in existing_assignees}
        target_sids = set(student_ids)

        to_remove = [a for a in existing_assignees if a.student_id not in target_sids]
        for a in to_remove:
            db.session.delete(a)
            research_cache.invalidate_student(a.student_id)

        to_add = target_sids - existing_sids
        for sid in to_add:
            st = db.session.get(ResearchStudentProfile, sid)
            if st:
                db.session.add(ResearchTaskAssignee(task_id=task.id, student_id=st.id))
                research_cache.invalidate_student(st.id)
                if app:
                    ResearchEmailService.notify_task_assigned(
                        app=app,
                        student=st,
                        task=task,
                        project=task.milestone.project,
                    )

        db.session.commit()
        research_cache.invalidate_task(task.id)
        research_cache.invalidate_project(task.project_id)
        research_cache.invalidate_faculty(faculty.id)
        return task.to_dict()

    @classmethod
    def get_project_milestones(cls, project_id: int, user_id: int) -> List[Dict[str, Any]]:
        """
        Ultra-fast cached retrieval of project milestones and nested tasks.
        """
        cache_key = f"milestones:project:{project_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        user = db.session.get(User, user_id)
        project = db.session.get(ResearchProject, project_id)
        if not project:
            raise ResearchNotFoundError("Project not found.")

        milestones = (
            ResearchMilestone.query.filter_by(project_id=project_id)
            .options(
                selectinload(ResearchMilestone.tasks).selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student),
                selectinload(ResearchMilestone.assignees).joinedload(ResearchMilestoneAssignee.student),
            )
            .order_by(ResearchMilestone.created_at.asc())
            .all()
        )
        res = [m.to_dict(include_tasks=True) for m in milestones]
        research_cache.set(cache_key, res, tags=[f"project:{project_id}"])
        return res

    @classmethod
    def get_milestone_tasks(cls, milestone_id: int, user_id: int) -> List[Dict[str, Any]]:
        """
        Ultra-fast cached retrieval of milestone tasks.
        """
        cache_key = f"tasks:milestone:{milestone_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        milestone = db.session.get(ResearchMilestone, milestone_id)
        if not milestone:
            raise ResearchNotFoundError("Milestone not found.")

        tasks = (
            ResearchTask.query.filter_by(milestone_id=milestone_id)
            .options(
                selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student).joinedload(ResearchStudentProfile.user),
                selectinload(ResearchTask.submissions),
            )
            .order_by(ResearchTask.created_at.asc())
            .all()
        )
        res = [t.to_dict() for t in tasks]
        research_cache.set(cache_key, res, tags=[f"project:{milestone.project_id}", f"milestone:{milestone_id}"])
        return res

    @classmethod
    def update_task_status(
        cls,
        task_id: int,
        user_id: int,
        status: str,
        progress_percentage: Optional[int] = None,
        notes: Optional[str] = None,
        app=None,
    ) -> Dict[str, Any]:
        user = db.session.get(User, user_id)
        task = db.session.get(ResearchTask, task_id)
        if not task:
            raise ResearchNotFoundError("Task not found.")

        is_faculty = user.is_faculty_coordinator()
        is_student = user.is_student_researcher()

        if is_faculty:
            faculty = cls.get_faculty_profile(user_id)
            if task.milestone.project.faculty_id != faculty.id:
                raise ResearchPermissionError("Unauthorized.")
        elif is_student:
            student = cls.get_student_profile(user_id)
            assignee = ResearchTaskAssignee.query.filter_by(task_id=task.id, student_id=student.id).first()
            if not assignee:
                raise ResearchPermissionError("You are not assigned to this task.")
        else:
            raise ResearchPermissionError("Unauthorized.")

        task.status = status
        if progress_percentage is not None:
            task.progress_percentage = max(0, min(100, progress_percentage))

        if is_faculty and app:
            faculty = task.milestone.project.faculty
            for assignee in task.assignees:
                st = assignee.student
                if status == "approved":
                    ResearchEmailService.notify_submission_approved(app, st, task, faculty)
                elif status == "revision_requested":
                    ResearchEmailService.notify_revision_requested(app, st, task, faculty, notes or "Revisions requested.")

        db.session.commit()
        research_cache.invalidate_task(task.id)
        research_cache.invalidate_project(task.project_id)
        if task.milestone and task.milestone.project:
            research_cache.invalidate_faculty(task.milestone.project.faculty_id)
        for a in task.assignees:
            research_cache.invalidate_student(a.student_id)
        return task.to_dict()

    # -------------------------------------------------------------------------
    # Progress Submissions & Two-Way Feedback Conversation Thread
    # -------------------------------------------------------------------------

    @classmethod
    def submit_progress(
        cls,
        task_id: int,
        user_id: int,
        data: Dict[str, Any],
        app=None,
    ) -> Dict[str, Any]:
        student = cls.get_student_profile(user_id)
        task = db.session.get(ResearchTask, task_id)
        if not task:
            raise ResearchNotFoundError("Task not found.")

        assignee = ResearchTaskAssignee.query.filter_by(task_id=task.id, student_id=student.id).first()
        if not assignee:
            raise ResearchPermissionError("You are not assigned to this task.")

        pct = int(data.get("work_completed_percentage", task.progress_percentage or 0))
        pct = max(0, min(100, pct))
        task.progress_percentage = pct
        task.status = "submitted_for_review"

        work_text = (data.get("notes") or data.get("work_completed") or "Progress update submission").strip()
        submission = ResearchProgressSubmission(
            task_id=task.id,
            milestone_id=task.milestone_id,
            student_id=student.id,
            progress_percentage=pct,
            papers_reviewed=data.get("papers_reviewed_count") or data.get("papers_reviewed"),
            citations_prepared=data.get("citations_count") or data.get("citations_prepared"),
            work_completed=work_text,
            challenges=(data.get("challenges_faced") or data.get("challenges") or "").strip(),
            next_steps=(data.get("next_steps") or "").strip(),
            status=ResearchProgressSubmission.STATUS_SUBMITTED,
        )
        db.session.add(submission)
        db.session.flush()

        thread = ResearchFeedbackThread.query.filter_by(task_id=task.id).first()
        if not thread:
            thread = ResearchFeedbackThread(
                task_id=task.id,
                milestone_id=task.milestone_id,
                project_id=task.project_id,
                student_id=student.id,
                faculty_id=task.project.faculty_id,
            )
            db.session.add(thread)
            db.session.flush()

        summary_msg = (
            f"Progress Submission ({pct}% completed)\n"
            f"Work: {submission.work_completed}\n"
            f"Challenges: {submission.challenges or 'None'}\n"
            f"Next Steps: {submission.next_steps or 'None'}"
        )
        msg = ResearchFeedbackMessage(
            thread_id=thread.id,
            sender_user_id=user_id,
            sender_role="student_researcher",
            message_text=summary_msg,
            message_type="submission_note",
            action_decision="submitted_for_review",
        )
        db.session.add(msg)
        db.session.flush()

        attachment_items = data.get("attachments") or []
        for att in attachment_items:
            new_att = ResearchAttachment(
                project_id=task.project_id,
                task_id=task.id,
                submission_id=submission.id,
                message_id=msg.id,
                uploaded_by_user_id=user_id,
                storage_provider="local",
                file_name=att.get("file_name", "submission_file"),
                file_type=att.get("file_type", "document"),
                file_size=att.get("file_size", 0),
                storage_path=att.get("storage_path") or att.get("file_url") or "",
                description=att.get("description"),
            )
            db.session.add(new_att)

        faculty_user_id = task.project.faculty.user_id
        notif = ResearchNotification(
            user_id=faculty_user_id,
            title=f"Submission: {task.title}",
            body=f"{student.full_name} submitted a progress update ({pct}%) for review.",
            notification_type="submission_submitted",
            reference_id=task.id,
            reference_type="task",
        )
        db.session.add(notif)
        db.session.commit()

        research_cache.invalidate_task(task.id)
        research_cache.invalidate_project(task.project_id)
        research_cache.invalidate_faculty(task.project.faculty_id)
        research_cache.invalidate_student(student.id)
        research_cache.invalidate_tag(f"user_notifs:{faculty_user_id}")

        res = submission.to_dict()
        res["work_completed_percentage"] = submission.progress_percentage
        return res

    @classmethod
    def add_feedback_message(
        cls,
        task_id: int,
        user_id: int,
        data: Dict[str, Any],
        app=None,
    ) -> Dict[str, Any]:
        user = db.session.get(User, user_id)
        task = db.session.get(ResearchTask, task_id)
        if not task:
            raise ResearchNotFoundError("Task not found.")

        thread = ResearchFeedbackThread.query.filter_by(task_id=task.id).first()
        if not thread:
            assignee = task.assignees[0] if task.assignees else None
            student_id = assignee.student_id if assignee else 1
            thread = ResearchFeedbackThread(
                task_id=task.id,
                milestone_id=task.milestone_id,
                project_id=task.project_id,
                student_id=student_id,
                faculty_id=task.project.faculty_id,
            )
            db.session.add(thread)
            db.session.flush()

        message_text = (data.get("message") or data.get("message_text") or "").strip()
        action = data.get("action", "comment")

        msg = ResearchFeedbackMessage(
            thread_id=thread.id,
            sender_user_id=user_id,
            sender_role=user.role,
            message_text=message_text,
            message_type="revision_request" if action == "request_revision" else ("approval" if action == "approve" else "comment"),
            action_decision=action,
        )
        db.session.add(msg)
        db.session.flush()

        if user.is_faculty_coordinator():
            faculty = cls.get_faculty_profile(user_id)
            if action == "approve":
                task.status = "approved"
                task.progress_percentage = 100
                if app:
                    for a in task.assignees:
                        ResearchEmailService.notify_submission_approved(app, a.student, task, faculty)
            elif action == "request_revision":
                task.status = "revision_requested"
                if app:
                    for a in task.assignees:
                        ResearchEmailService.notify_revision_requested(app, a.student, task, faculty, message_text)
            else:
                if app:
                    for a in task.assignees:
                        ResearchEmailService.notify_faculty_feedback_added(app, a.student, task, faculty, message_text)

        elif user.is_student_researcher():
            student = cls.get_student_profile(user_id)
            faculty_user_id = task.project.faculty.user_id
            db.session.add(ResearchNotification(
                user_id=faculty_user_id,
                title=f"Student Reply: {task.title}",
                body=f"{student.full_name} replied: {message_text[:60]}",
                notification_type="student_reply",
                reference_id=task.id,
                reference_type="task",
            ))
            research_cache.invalidate_tag(f"user_notifs:{faculty_user_id}")

        attachment_items = data.get("attachments") or []
        for att in attachment_items:
            new_att = ResearchAttachment(
                project_id=task.project_id,
                task_id=task.id,
                message_id=msg.id,
                uploaded_by_user_id=user_id,
                storage_provider="local",
                file_name=att.get("file_name", "feedback_file"),
                file_type=att.get("file_type", "document"),
                file_size=att.get("file_size", 0),
                storage_path=att.get("storage_path") or att.get("file_url") or "",
                description=att.get("description"),
            )
            db.session.add(new_att)

        db.session.commit()
        research_cache.invalidate_task(task.id)
        if task.project:
            research_cache.invalidate_faculty(task.project.faculty_id)
            research_cache.invalidate_project(task.project_id)
        for a in task.assignees:
            research_cache.invalidate_student(a.student_id)
        return msg.to_dict()

    @classmethod
    def get_task_feedback_thread(cls, task_id: int, user_id: int) -> Dict[str, Any]:
        cache_key = f"thread:task:{task_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        task = db.session.get(ResearchTask, task_id)
        if not task:
            raise ResearchNotFoundError("Task not found.")

        thread = ResearchFeedbackThread.query.filter_by(task_id=task.id).first()
        if not thread:
            res = {
                "thread_id": None,
                "task_id": task.id,
                "task_title": task.title,
                "task_status": task.status,
                "progress_percentage": task.progress_percentage,
                "messages": [],
            }
            research_cache.set(cache_key, res, tags=[f"task:{task_id}"])
            return res

        messages = (
            ResearchFeedbackMessage.query.filter_by(thread_id=thread.id)
            .order_by(ResearchFeedbackMessage.created_at.asc())
            .all()
        )
        res = {
            "thread_id": thread.id,
            "task_id": task.id,
            "task_title": task.title,
            "task_status": task.status,
            "progress_percentage": task.progress_percentage,
            "messages": [m.to_dict() for m in messages],
        }
        research_cache.set(cache_key, res, tags=[f"task:{task_id}"])
        return res

    # -------------------------------------------------------------------------
    # Meeting Scheduler
    # -------------------------------------------------------------------------

    @classmethod
    def schedule_meeting(cls, user_id: int, data: Dict[str, Any], app=None) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        title = (data.get("title") or "").strip()
        if not title:
            raise ResearchServiceError("Meeting title is required.")

        meeting_dt = None
        date_raw = data.get("scheduled_at") or data.get("meeting_datetime")
        if date_raw:
            try:
                meeting_dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            except Exception:
                pass
        if not meeting_dt:
            raise ResearchServiceError("A valid meeting date and time is required.")

        loc_link = (data.get("location_or_link") or data.get("location") or data.get("meeting_link") or "Online").strip()
        meeting = ResearchMeeting(
            faculty_id=faculty.id,
            team_id=data.get("team_id"),
            project_id=data.get("project_id"),
            title=title,
            agenda=(data.get("agenda") or "").strip(),
            scheduled_at=meeting_dt,
            duration_minutes=int(data.get("duration_minutes", 60)),
            location_or_link=loc_link,
            meeting_notes=(data.get("meeting_notes") or data.get("notes") or "").strip(),
            status="scheduled",
        )
        db.session.add(meeting)
        db.session.flush()

        student_ids = data.get("participant_student_ids") or []
        for sid in student_ids:
            st = db.session.get(ResearchStudentProfile, sid)
            if st:
                db.session.add(ResearchMeetingParticipant(meeting_id=meeting.id, student_id=st.id, attendance_status="invited"))
                if app:
                    ResearchEmailService.notify_meeting_scheduled(
                        app=app,
                        recipient_email=st.email,
                        recipient_user_id=st.user_id,
                        recipient_name=st.full_name,
                        meeting=meeting,
                        faculty=faculty,
                        is_update=False,
                    )

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        for sid in student_ids:
            research_cache.invalidate_student(sid)
        return meeting.to_dict()

    @classmethod
    def update_meeting(cls, meeting_id: int, user_id: int, data: Dict[str, Any], app=None) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        meeting = db.session.get(ResearchMeeting, meeting_id)
        if not meeting or meeting.faculty_id != faculty.id:
            raise ResearchPermissionError("Meeting not found or not owned by you.")

        if "title" in data and data["title"]:
            meeting.title = data["title"].strip()
        if "agenda" in data:
            meeting.agenda = (data["agenda"] or "").strip()
        date_raw = data.get("scheduled_at") or data.get("meeting_datetime")
        if date_raw:
            try:
                meeting.scheduled_at = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            except Exception:
                pass
        if "duration_minutes" in data:
            meeting.duration_minutes = int(data["duration_minutes"])
        if "location_or_link" in data or "location" in data or "meeting_link" in data:
            meeting.location_or_link = (data.get("location_or_link") or data.get("location") or data.get("meeting_link") or "").strip()
        if "meeting_notes" in data or "notes" in data:
            meeting.meeting_notes = (data.get("meeting_notes") or data.get("notes") or "").strip()
        if "status" in data:
            meeting.status = data["status"]

        if app:
            for p in meeting.participants:
                st = p.student
                ResearchEmailService.notify_meeting_scheduled(
                    app=app,
                    recipient_email=st.email,
                    recipient_user_id=st.user_id,
                    recipient_name=st.full_name,
                    meeting=meeting,
                    faculty=faculty,
                    is_update=True,
                )

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        for p in meeting.participants:
            research_cache.invalidate_student(p.student_id)
        return meeting.to_dict()

    @classmethod
    def record_meeting_attendance(
        cls,
        meeting_id: int,
        user_id: int,
        attendance_records: List[Dict[str, Any]],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        faculty = cls.get_faculty_profile(user_id)
        meeting = db.session.get(ResearchMeeting, meeting_id)
        if not meeting or meeting.faculty_id != faculty.id:
            raise ResearchPermissionError("Meeting not found or not owned by you.")

        if notes is not None:
            meeting.meeting_notes = notes.strip()

        for rec in attendance_records:
            sid = rec.get("student_id")
            part = ResearchMeetingParticipant.query.filter_by(meeting_id=meeting.id, student_id=sid).first()
            if part:
                part.attendance_status = rec.get("attendance_status", "present")

        db.session.commit()
        research_cache.invalidate_faculty(faculty.id)
        for p in meeting.participants:
            research_cache.invalidate_student(p.student_id)

        res = meeting.to_dict()
        res["notes"] = meeting.meeting_notes
        return res

    @classmethod
    def get_meetings(cls, user_id: int) -> List[Dict[str, Any]]:
        user = db.session.get(User, user_id)
        if not user:
            raise ResearchPermissionError("Unauthorized.")

        is_faculty = user.is_faculty_coordinator()
        is_student = user.is_student_researcher()
        role_type = "faculty" if is_faculty else ("student" if is_student else "admin")
        cache_key = f"meetings:{role_type}:{user_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        eager_opts = [
            joinedload(ResearchMeeting.faculty),
            joinedload(ResearchMeeting.team),
            joinedload(ResearchMeeting.project),
            selectinload(ResearchMeeting.participants).joinedload(ResearchMeetingParticipant.student).joinedload(ResearchStudentProfile.user),
        ]

        if is_faculty:
            faculty = cls.get_faculty_profile(user_id)
            meetings = (
                ResearchMeeting.query.filter_by(faculty_id=faculty.id)
                .options(*eager_opts)
                .order_by(ResearchMeeting.scheduled_at.asc())
                .all()
            )
            res = [m.to_dict() for m in meetings]
            research_cache.set(cache_key, res, tags=[f"faculty:{faculty.id}", "global:meetings"])
            return res

        elif is_student:
            student = cls.get_student_profile(user_id)
            participations = ResearchMeetingParticipant.query.filter_by(student_id=student.id).all()
            meeting_ids = [p.meeting_id for p in participations]
            if not meeting_ids:
                research_cache.set(cache_key, [], tags=[f"student:{student.id}", "global:meetings"])
                return []
            meetings = (
                ResearchMeeting.query.filter(ResearchMeeting.id.in_(meeting_ids))
                .options(*eager_opts)
                .order_by(ResearchMeeting.scheduled_at.asc())
                .all()
            )
            res = [m.to_dict() for m in meetings]
            research_cache.set(cache_key, res, tags=[f"student:{student.id}", "global:meetings"])
            return res

        return []

    # -------------------------------------------------------------------------
    # Student Researcher Portal Dashboard Summary
    # -------------------------------------------------------------------------

    @classmethod
    def get_student_dashboard_overview(cls, user_id: int) -> Dict[str, Any]:
        student_id = cls.get_student_id(user_id)
        cache_key = f"student_overview:{student_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        student = cls.get_student_profile(user_id)

        # 1. Teams with eager loading
        memberships = (
            ResearchTeamMember.query.filter_by(student_id=student.id, is_active=True)
            .options(
                joinedload(ResearchTeamMember.team).joinedload(ResearchTeam.faculty),
            )
            .all()
        )
        teams = [m.team.to_dict(include_members=True, include_projects=False) for m in memberships if m.team and m.team.is_active]

        # 2. Projects with eager loading
        proj_memberships = ResearchProjectMember.query.filter_by(student_id=student.id).all()
        proj_ids = [pm.project_id for pm in proj_memberships]
        projects = []
        if proj_ids:
            p_records = (
                ResearchProject.query.filter(
                    ResearchProject.id.in_(proj_ids),
                    ResearchProject.is_archived == False,
                )
                .options(
                    joinedload(ResearchProject.team),
                    joinedload(ResearchProject.faculty),
                    selectinload(ResearchProject.milestones).selectinload(ResearchMilestone.tasks).selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student),
                )
                .all()
            )
            projects = [p.to_dict(include_milestones=True, include_members=False) for p in p_records]

        # 3. Tasks with eager loading
        task_assignees = (
            ResearchTaskAssignee.query.filter_by(student_id=student.id)
            .options(
                joinedload(ResearchTaskAssignee.task).joinedload(ResearchTask.project),
                joinedload(ResearchTaskAssignee.task).joinedload(ResearchTask.milestone),
                joinedload(ResearchTaskAssignee.task).selectinload(ResearchTask.assignees).joinedload(ResearchTaskAssignee.student),
            )
            .all()
        )
        tasks = [ta.task.to_dict() for ta in task_assignees if ta.task]

        # 4. Meetings with eager loading
        now = datetime.now(timezone.utc)
        participations = (
            ResearchMeetingParticipant.query.filter_by(student_id=student.id)
            .options(
                joinedload(ResearchMeetingParticipant.meeting).joinedload(ResearchMeeting.faculty),
                joinedload(ResearchMeetingParticipant.meeting).selectinload(ResearchMeeting.participants).joinedload(ResearchMeetingParticipant.student),
            )
            .all()
        )
        meeting_objs = [p.meeting for p in participations if p.meeting and p.meeting.scheduled_at and p.meeting.scheduled_at >= now]
        meeting_objs.sort(key=lambda m: m.scheduled_at)
        meetings = [m.to_dict() for m in meeting_objs[:5]]

        # 5. Notifications
        notifs = (
            ResearchNotification.query.filter_by(user_id=user_id)
            .order_by(ResearchNotification.created_at.desc())
            .limit(10)
            .all()
        )

        res = {
            "student_profile": student.to_dict(),
            "teams": teams,
            "projects": projects,
            "tasks": tasks,
            "upcoming_meetings": meetings,
            "notifications": [n.to_dict() for n in notifs],
        }
        research_cache.set(cache_key, res, tags=[f"student:{student.id}"])
        return res

    # -------------------------------------------------------------------------
    # In-App Notifications
    # -------------------------------------------------------------------------

    @classmethod
    def get_notifications(cls, user_id: int) -> List[Dict[str, Any]]:
        cache_key = f"notifs:user:{user_id}"
        cached = research_cache.get(cache_key)
        if cached is not None:
            return cached

        notifs = (
            ResearchNotification.query.filter_by(user_id=user_id)
            .order_by(ResearchNotification.created_at.desc())
            .limit(30)
            .all()
        )
        res = [n.to_dict() for n in notifs]
        research_cache.set(cache_key, res, ttl=30, tags=[f"user_notifs:{user_id}"])
        return res

    @classmethod
    def mark_notification_read(cls, notif_id: int, user_id: int) -> bool:
        n = ResearchNotification.query.filter_by(id=notif_id, user_id=user_id).first()
        if n:
            n.is_read = True
            db.session.commit()
            research_cache.invalidate_tag(f"user_notifs:{user_id}")
            return True
        return False
