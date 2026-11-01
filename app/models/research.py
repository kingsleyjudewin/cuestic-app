import json
from typing import Optional, List, Dict
from sqlalchemy import UniqueConstraint
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class FacultyProfile(db.Model):
    """Faculty research coordinator profile linked to a user account."""
    __tablename__ = "faculty_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    department = db.Column(db.String(150), default="Electronics and Communication Engineering", nullable=False)
    designation = db.Column(db.String(100), default="Faculty Coordinator", nullable=True)
    specialization = db.Column(db.String(255), nullable=True)
    research_interests = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    profile_image_url = db.Column(db.String(500), nullable=True)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = db.relationship("User", back_populates="faculty_profile")
    teams = db.relationship("ResearchTeam", back_populates="faculty", cascade="all, delete-orphan", lazy="dynamic")
    projects = db.relationship("ResearchProject", back_populates="faculty", cascade="all, delete-orphan", lazy="dynamic")
    meetings = db.relationship("ResearchMeeting", back_populates="faculty", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "email": self.user.email if self.user else None,
            "full_name": self.full_name,
            "department": self.department,
            "designation": self.designation,
            "specialization": self.specialization,
            "research_interests": self.research_interests,
            "bio": self.bio,
            "phone_number": self.phone_number,
            "profile_image_url": self.profile_image_url,
            "must_change_password": self.must_change_password,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class ResearchStudentProfile(db.Model):
    """Student researcher profile with dedicated research login identity."""
    __tablename__ = "research_student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    department = db.Column(db.String(150), default="Electronics and Communication Engineering", nullable=False)
    programme = db.Column(db.String(100), default="B.Tech ECE", nullable=False)
    semester = db.Column(db.String(30), default="Semester 5", nullable=False)
    phone_number = db.Column(db.String(30), nullable=True)
    profile_image_url = db.Column(db.String(500), nullable=True)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = db.relationship("User", back_populates="research_student_profile")
    linked_member = db.relationship("Member", foreign_keys=[member_id])
    team_memberships = db.relationship("ResearchTeamMember", back_populates="student", cascade="all, delete-orphan", lazy="dynamic")
    project_memberships = db.relationship("ResearchProjectMember", back_populates="student", cascade="all, delete-orphan", lazy="dynamic")
    task_assignments = db.relationship("ResearchTaskAssignee", back_populates="student", cascade="all, delete-orphan", lazy="dynamic")
    submissions = db.relationship("ResearchProgressSubmission", back_populates="student", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "member_id": self.member_id,
            "full_name": self.full_name,
            "registration_number": self.registration_number,
            "email": self.email,
            "department": self.department,
            "programme": self.programme,
            "semester": self.semester,
            "phone_number": self.phone_number,
            "profile_image_url": self.profile_image_url,
            "must_change_password": self.must_change_password,
            "is_active": self.is_active,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class ResearchTeam(db.Model):
    """A research lab/group created and managed by a Faculty Coordinator."""
    __tablename__ = "research_teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    objectives = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    faculty = db.relationship("FacultyProfile", back_populates="teams")
    members = db.relationship("ResearchTeamMember", back_populates="team", cascade="all, delete-orphan", lazy="dynamic")
    projects = db.relationship("ResearchProject", back_populates="team", cascade="all, delete-orphan", lazy="dynamic")
    meetings = db.relationship("ResearchMeeting", back_populates="team", cascade="all, delete-orphan", lazy="dynamic")

    def get_tags(self) -> List[str]:
        if not self.tags_json:
            return []
        try:
            return json.loads(self.tags_json)
        except Exception:
            return []

    def set_tags(self, tags: List[str]):
        self.tags_json = json.dumps(tags) if tags else None

    def to_dict(
        self,
        include_members: bool = False,
        include_projects: bool = False,
        member_count: Optional[int] = None,
        project_count: Optional[int] = None,
    ) -> dict:
        m_count = member_count if member_count is not None else self.members.filter_by(is_active=True).count()
        p_count = project_count if project_count is not None else self.projects.filter_by(is_archived=False).count()
        data = {
            "id": self.id,
            "name": self.name,
            "faculty_id": self.faculty_id,
            "faculty_name": self.faculty.full_name if self.faculty else None,
            "domain": self.domain,
            "description": self.description,
            "objectives": self.objectives,
            "tags": self.get_tags(),
            "is_active": self.is_active,
            "member_count": m_count,
            "project_count": p_count,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_members:
            active_m = self.members.filter_by(is_active=True).all()
            data["members"] = [m.to_dict() for m in active_m]
        if include_projects:
            active_p = self.projects.filter_by(is_archived=False).all()
            data["projects"] = [p.to_dict(include_milestones=False) for p in active_p]
        return data


class ResearchTeamMember(db.Model):
    """Membership mapping of a Student Researcher inside a Research Team."""
    __tablename__ = "research_team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "student_id", name="uq_research_team_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("research_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    team = db.relationship("ResearchTeam", back_populates="members")
    student = db.relationship("ResearchStudentProfile", back_populates="team_memberships")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "student_id": self.student_id,
            "student": self.student.to_dict() if self.student else None,
            "joined_at": format_iso_utc(self.joined_at),
            "is_active": self.is_active,
        }


class ResearchProject(db.Model):
    """Research Project under a Research Team."""
    __tablename__ = "research_projects"

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_ON_HOLD = "on_hold"
    STATUS_ARCHIVED = "archived"

    ALL_STATUSES = (STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_ON_HOLD, STATUS_ARCHIVED)

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("research_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    research_problem = db.Column(db.Text, nullable=True)
    objectives = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    expected_completion_date = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(30), default=STATUS_IN_PROGRESS, nullable=False, index=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    team = db.relationship("ResearchTeam", back_populates="projects")
    faculty = db.relationship("FacultyProfile", back_populates="projects")
    members = db.relationship("ResearchProjectMember", back_populates="project", cascade="all, delete-orphan", lazy="dynamic")
    milestones = db.relationship("ResearchMilestone", back_populates="project", cascade="all, delete-orphan", order_by="ResearchMilestone.due_date")
    tasks = db.relationship("ResearchTask", back_populates="project", cascade="all, delete-orphan")
    attachments = db.relationship("ResearchAttachment", back_populates="project", cascade="all, delete-orphan", lazy="dynamic")
    meetings = db.relationship("ResearchMeeting", back_populates="project", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, include_milestones: bool = True, include_members: bool = True) -> dict:
        data = {
            "id": self.id,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "faculty_id": self.faculty_id,
            "faculty_name": self.faculty.full_name if self.faculty else None,
            "title": self.title,
            "research_problem": self.research_problem,
            "objectives": self.objectives,
            "description": self.description,
            "start_date": format_iso_utc(self.start_date) if self.start_date else None,
            "expected_completion_date": format_iso_utc(self.expected_completion_date) if self.expected_completion_date else None,
            "status": self.status,
            "is_archived": self.is_archived,
            "milestone_count": len(self.milestones) if self.milestones else 0,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_members:
            data["members"] = [m.to_dict() for m in self.members.all()]
        if include_milestones:
            data["milestones"] = [m.to_dict(include_tasks=True) for m in self.milestones]
        return data


class ResearchProjectMember(db.Model):
    """Students assigned to a specific research project."""
    __tablename__ = "research_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "student_id", name="uq_research_project_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(50), default="Student Researcher", nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    project = db.relationship("ResearchProject", back_populates="members")
    student = db.relationship("ResearchStudentProfile", back_populates="project_memberships")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "student_id": self.student_id,
            "role": self.role,
            "student": self.student.to_dict() if self.student else None,
            "assigned_at": format_iso_utc(self.assigned_at),
        }


class ResearchMilestone(db.Model):
    """Major research phase or goal within a Project."""
    __tablename__ = "research_milestones"

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_REVISION_REQUESTED = "revision_requested"
    STATUS_APPROVED = "approved"
    STATUS_OVERDUE = "overdue"

    ALL_STATUSES = (
        STATUS_NOT_STARTED,
        STATUS_IN_PROGRESS,
        STATUS_SUBMITTED,
        STATUS_REVISION_REQUESTED,
        STATUS_APPROVED,
        STATUS_OVERDUE,
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_criteria = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(30), default=STATUS_NOT_STARTED, nullable=False, index=True)
    completion_percentage = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project = db.relationship("ResearchProject", back_populates="milestones")
    assignees = db.relationship("ResearchMilestoneAssignee", back_populates="milestone", cascade="all, delete-orphan")
    tasks = db.relationship("ResearchTask", back_populates="milestone", cascade="all, delete-orphan", order_by="ResearchTask.due_date")

    def to_dict(self, include_tasks: bool = True) -> dict:
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "project_title": self.project.title if self.project else None,
            "title": self.title,
            "description": self.description,
            "target_criteria": self.target_criteria,
            "start_date": format_iso_utc(self.start_date) if self.start_date else None,
            "due_date": format_iso_utc(self.due_date) if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "completion_percentage": self.completion_percentage,
            "assignees": [a.to_dict() for a in self.assignees],
            "task_count": len(self.tasks) if self.tasks else 0,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_tasks:
            data["tasks"] = [t.to_dict() for t in self.tasks]
        return data


class ResearchMilestoneAssignee(db.Model):
    """Students assigned to a Research Milestone."""
    __tablename__ = "research_milestone_assignees"
    __table_args__ = (
        UniqueConstraint("milestone_id", "student_id", name="uq_research_milestone_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("research_milestones.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    milestone = db.relationship("ResearchMilestone", back_populates="assignees")
    student = db.relationship("ResearchStudentProfile")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "milestone_id": self.milestone_id,
            "student_id": self.student_id,
            "student": self.student.to_dict() if self.student else None,
        }


class ResearchTask(db.Model):
    """Individual actionable task under a Milestone / Project."""
    __tablename__ = "research_tasks"

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED_FOR_REVIEW = "submitted_for_review"
    STATUS_REVISION_REQUESTED = "revision_requested"
    STATUS_APPROVED = "approved"
    STATUS_OVERDUE = "overdue"

    ALL_STATUSES = (
        STATUS_NOT_STARTED,
        STATUS_IN_PROGRESS,
        STATUS_SUBMITTED_FOR_REVIEW,
        STATUS_REVISION_REQUESTED,
        STATUS_APPROVED,
        STATUS_OVERDUE,
    )

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("research_milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(30), default=STATUS_NOT_STARTED, nullable=False, index=True)
    progress_percentage = db.Column(db.Integer, default=0, nullable=False)
    completion_criteria = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    milestone = db.relationship("ResearchMilestone", back_populates="tasks")
    project = db.relationship("ResearchProject", back_populates="tasks")
    assignees = db.relationship("ResearchTaskAssignee", back_populates="task", cascade="all, delete-orphan")
    submissions = db.relationship("ResearchProgressSubmission", back_populates="task", cascade="all, delete-orphan", order_by="desc(ResearchProgressSubmission.created_at)")
    feedback_threads = db.relationship("ResearchFeedbackThread", back_populates="task", cascade="all, delete-orphan")
    attachments = db.relationship("ResearchAttachment", back_populates="task", cascade="all, delete-orphan")

    def to_dict(self, include_submissions: bool = False) -> dict:
        data = {
            "id": self.id,
            "milestone_id": self.milestone_id,
            "milestone_title": self.milestone.title if self.milestone else None,
            "project_id": self.project_id,
            "project_title": self.project.title if self.project else None,
            "title": self.title,
            "instructions": self.instructions,
            "start_date": format_iso_utc(self.start_date) if self.start_date else None,
            "due_date": format_iso_utc(self.due_date) if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "completion_criteria": self.completion_criteria,
            "assignees": [a.to_dict() for a in self.assignees],
            "submission_count": len(self.submissions) if self.submissions else 0,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_submissions:
            data["submissions"] = [s.to_dict() for s in self.submissions]
        return data


class ResearchTaskAssignee(db.Model):
    """Students assigned to an individual Research Task."""
    __tablename__ = "research_task_assignees"
    __table_args__ = (
        UniqueConstraint("task_id", "student_id", name="uq_research_task_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    task = db.relationship("ResearchTask", back_populates="assignees")
    student = db.relationship("ResearchStudentProfile", back_populates="task_assignments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "student_id": self.student_id,
            "student": self.student.to_dict() if self.student else None,
        }


class ResearchProgressSubmission(db.Model):
    """Student progress update or formal review submission for a task/milestone."""
    __tablename__ = "research_progress_submissions"

    STATUS_SUBMITTED = "submitted_for_review"
    STATUS_REVIEWED = "reviewed"
    STATUS_REVISION_REQUESTED = "revision_requested"
    STATUS_APPROVED = "approved"

    ALL_STATUSES = (STATUS_SUBMITTED, STATUS_REVIEWED, STATUS_REVISION_REQUESTED, STATUS_APPROVED)

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("research_milestones.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percentage = db.Column(db.Integer, default=0, nullable=False)
    papers_reviewed = db.Column(db.Integer, nullable=True)
    citations_prepared = db.Column(db.Integer, nullable=True)
    work_completed = db.Column(db.Text, nullable=False)
    challenges = db.Column(db.Text, nullable=True)
    next_steps = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default=STATUS_SUBMITTED, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    task = db.relationship("ResearchTask", back_populates="submissions")
    student = db.relationship("ResearchStudentProfile", back_populates="submissions")
    attachments = db.relationship("ResearchAttachment", back_populates="submission", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "milestone_id": self.milestone_id,
            "student_id": self.student_id,
            "student_name": self.student.full_name if self.student else None,
            "progress_percentage": self.progress_percentage,
            "papers_reviewed": self.papers_reviewed,
            "citations_prepared": self.citations_prepared,
            "work_completed": self.work_completed,
            "challenges": self.challenges,
            "next_steps": self.next_steps,
            "status": self.status,
            "attachments": [a.to_dict() for a in self.attachments],
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class ResearchFeedbackThread(db.Model):
    """Conversation thread between faculty and student regarding a task, milestone or project."""
    __tablename__ = "research_feedback_threads"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("research_milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    task = db.relationship("ResearchTask", back_populates="feedback_threads")
    student = db.relationship("ResearchStudentProfile")
    faculty = db.relationship("FacultyProfile")
    messages = db.relationship("ResearchFeedbackMessage", back_populates="thread", cascade="all, delete-orphan", order_by="ResearchFeedbackMessage.created_at")

    def to_dict(self, include_messages: bool = True) -> dict:
        data = {
            "id": self.id,
            "task_id": self.task_id,
            "task_title": self.task.title if self.task else None,
            "milestone_id": self.milestone_id,
            "project_id": self.project_id,
            "student_id": self.student_id,
            "student_name": self.student.full_name if self.student else None,
            "faculty_id": self.faculty_id,
            "faculty_name": self.faculty.full_name if self.faculty else None,
            "message_count": len(self.messages) if self.messages else 0,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data


class ResearchFeedbackMessage(db.Model):
    """An individual entry (comment, revision request, approval, reply) in a feedback thread."""
    __tablename__ = "research_feedback_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("research_feedback_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_role = db.Column(db.String(30), nullable=False)  # faculty_coordinator, student_researcher
    message_text = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(30), default="comment", nullable=False)  # comment, revision_request, approval, submission_note
    action_decision = db.Column(db.String(30), nullable=True)  # approved, revision_requested
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    thread = db.relationship("ResearchFeedbackThread", back_populates="messages")
    sender = db.relationship("User")
    attachments = db.relationship("ResearchAttachment", back_populates="message", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        sender_name = None
        if self.sender:
            if hasattr(self.sender, "faculty_profile") and self.sender.faculty_profile:
                sender_name = self.sender.faculty_profile.full_name
            elif hasattr(self.sender, "research_student_profile") and self.sender.research_student_profile:
                sender_name = self.sender.research_student_profile.full_name
            else:
                sender_name = self.sender.username

        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "sender_user_id": self.sender_user_id,
            "sender_name": sender_name,
            "sender_role": self.sender_role,
            "message_text": self.message_text,
            "message_type": self.message_type,
            "action_decision": self.action_decision,
            "attachments": [a.to_dict() for a in self.attachments],
            "created_at": format_iso_utc(self.created_at),
        }


class ResearchAttachment(db.Model):
    """Uploaded research file, dataset, paper, report, or guideline document."""
    __tablename__ = "research_attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("research_feedback_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("research_progress_submissions.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    storage_path = db.Column(db.String(500), nullable=False)
    storage_provider = db.Column(db.String(50), default="local", nullable=False)
    description = db.Column(db.Text, nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    project = db.relationship("ResearchProject", back_populates="attachments")
    task = db.relationship("ResearchTask", back_populates="attachments")
    submission = db.relationship("ResearchProgressSubmission", back_populates="attachments")
    message = db.relationship("ResearchFeedbackMessage", back_populates="attachments")
    uploader = db.relationship("User")

    def to_dict(self) -> dict:
        uploader_name = self.uploader.username if self.uploader else None
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "submission_id": self.submission_id,
            "message_id": self.message_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "storage_path": self.storage_path,
            "storage_provider": self.storage_provider,
            "description": self.description,
            "uploaded_by_user_id": self.uploaded_by_user_id,
            "uploaded_by_name": uploader_name,
            "created_at": format_iso_utc(self.created_at),
        }


class ResearchMeeting(db.Model):
    """Scheduled research review or group meeting."""
    __tablename__ = "research_meetings"

    STATUS_SCHEDULED = "scheduled"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    ALL_STATUSES = (STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CANCELLED)

    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("research_teams.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    agenda = db.Column(db.Text, nullable=True)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)
    location_or_link = db.Column(db.Text, nullable=True)
    meeting_notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default=STATUS_SCHEDULED, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    faculty = db.relationship("FacultyProfile", back_populates="meetings")
    team = db.relationship("ResearchTeam", back_populates="meetings")
    project = db.relationship("ResearchProject", back_populates="meetings")
    participants = db.relationship("ResearchMeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "faculty_id": self.faculty_id,
            "faculty_name": self.faculty.full_name if self.faculty else None,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "project_id": self.project_id,
            "project_title": self.project.title if self.project else None,
            "title": self.title,
            "agenda": self.agenda,
            "scheduled_at": format_iso_utc(self.scheduled_at),
            "duration_minutes": self.duration_minutes,
            "location_or_link": self.location_or_link,
            "meeting_notes": self.meeting_notes,
            "status": self.status,
            "participants": [p.to_dict() for p in self.participants],
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }


class ResearchMeetingParticipant(db.Model):
    """Students invited/attending a Research Meeting."""
    __tablename__ = "research_meeting_participants"
    __table_args__ = (
        UniqueConstraint("meeting_id", "student_id", name="uq_research_meeting_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("research_meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("research_student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_status = db.Column(db.String(20), default="invited", nullable=False)  # invited, present, absent, excused

    meeting = db.relationship("ResearchMeeting", back_populates="participants")
    student = db.relationship("ResearchStudentProfile")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "student_id": self.student_id,
            "student_name": self.student.full_name if self.student else None,
            "attendance_status": self.attendance_status,
        }


class ResearchNotification(db.Model):
    """In-app notifications for Faculty and Student Researchers."""
    __tablename__ = "research_notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False, index=True)
    reference_id = db.Column(db.Integer, nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    user = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "body": self.body,
            "notification_type": self.notification_type,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "is_read": self.is_read,
            "created_at": format_iso_utc(self.created_at),
        }


class ResearchEmailLog(db.Model):
    """Log and deduplication tracker for automated research email reminders."""
    __tablename__ = "research_email_logs"

    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False, index=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    subject = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(30), default="queued", nullable=False, index=True)  # queued, sent, failed, skipped
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    deduplication_key = db.Column(db.String(200), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipient_email": self.recipient_email,
            "recipient_user_id": self.recipient_user_id,
            "subject": self.subject,
            "event_type": self.event_type,
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "deduplication_key": self.deduplication_key,
            "created_at": format_iso_utc(self.created_at),
            "sent_at": format_iso_utc(self.sent_at),
        }
