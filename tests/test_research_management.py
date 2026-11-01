"""
End-to-end and unit tests for the Research Management System.
Covers:
- Faculty coordinator credentials & first login password change
- Faculty profile updates
- Research team creation, student addition, and member removal
- Centralized deduplicated student directory
- Project, milestone, and task workflows
- Student researcher progress submission & two-way continuous feedback thread
- Meeting scheduling and attendance
- IDOR security and RBAC permission isolation
"""
import pytest
from app.models.user import User
from app.models.research import (
    FacultyProfile,
    ResearchStudentProfile,
    ResearchTeam,
    ResearchProject,
    ResearchMilestone,
    ResearchTask,
    ResearchMeeting,
)
from scripts.seed_faculty_coordinators import seed_faculty


def login_user(client, username, password):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {username}: {resp.get_data(as_text=True)}"
    data = resp.get_json()["data"]
    token = data["token"]
    user = data["user"]
    return token, user


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_research_data(app):
    with app.app_context():
        seed_faculty(app)


class TestResearchManagementSystem:

    def test_01_faculty_initial_login_and_first_password_change(self, client):
        """Test initial login with seeded temporary credentials and mandatory first password change."""
        username = "eldho.paul"
        temp_pass = "Research2026!Eldho"

        token, user = login_user(client, username, temp_pass)
        assert user["role"] == User.ROLE_FACULTY_COORDINATOR
        assert user["must_change_password"] is True
        assert user["full_name"] == "Dr Eldho Paul"

        # Attempt to change to a new permanent password
        new_pass = "EldhoPermanent2026!Secure"
        resp = client.post(
            "/api/v1/research/auth/first-login-password",
            headers=auth_header(token),
            json={"current_password": temp_pass, "new_password": new_pass},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["user"]["must_change_password"] is False

        # Verify login now works with the new permanent password
        token2, user2 = login_user(client, username, new_pass)
        assert user2["must_change_password"] is False

    def test_02_faculty_profile_update(self, client):
        """Test faculty retrieving and updating profile information."""
        token, user = login_user(client, "eldho.paul", "Research2026!Eldho")

        # Get profile
        resp = client.get("/api/v1/research/profile", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["type"] == "faculty"
        assert data["profile"]["full_name"] == "Dr Eldho Paul"

        # Update profile
        resp = client.put(
            "/api/v1/research/faculty/profile",
            headers=auth_header(token),
            json={
                "bio": "Faculty researcher leading deep learning and edge AI initiatives.",
                "research_interests": "Deep Learning, Edge AI, Computer Vision, Transformers",
                "phone_number": "+91 9876543210",
            },
        )
        assert resp.status_code == 200
        updated = resp.get_json()["data"]
        assert "Edge AI" in updated["research_interests"]
        assert updated["phone_number"] == "+91 9876543210"

    def test_03_create_research_team_and_add_student(self, client):
        """Test creating research teams and adding a student researcher."""
        token, user = login_user(client, "eldho.paul", "Research2026!Eldho")

        # Create Team 1
        resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(token),
            json={
                "name": "Deep Learning Research Group",
                "domain": "Deep Learning & Computer Vision",
                "description": "Exploration of novel deep learning and generative vision models.",
                "objectives": "Publish 3 IEEE papers and develop edge prototypes.",
            },
        )
        assert resp.status_code == 201
        team1 = resp.get_json()["data"]
        team1_id = team1["id"]
        assert team1["name"] == "Deep Learning Research Group"

        # Add Student 1 to Team 1
        resp = client.post(
            f"/api/v1/research/teams/{team1_id}/students",
            headers=auth_header(token),
            json={
                "full_name": "Rohan Sharma",
                "registration_number": "2140101",
                "email": "rohan.sharma@christuniversity.in",
                "programme": "B.Tech ECE",
                "semester": "Semester 6",
            },
        )
        assert resp.status_code == 201
        res_data = resp.get_json()["data"]
        assert res_data["student"]["full_name"] == "Rohan Sharma"
        assert res_data["student"]["registration_number"] == "2140101"
        assert "temporary_password" in res_data

        # Create Team 2 under same faculty
        resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(token),
            json={
                "name": "Edge AI Systems Lab",
                "domain": "Embedded Intelligence",
                "description": "On-device inference on FPGA and microcontrollers.",
            },
        )
        assert resp.status_code == 201
        team2_id = resp.get_json()["data"]["id"]

        # Add same student (Rohan) to Team 2
        resp = client.post(
            f"/api/v1/research/teams/{team2_id}/students",
            headers=auth_header(token),
            json={
                "full_name": "Rohan Sharma",
                "registration_number": "2140101",
                "email": "rohan.sharma@christuniversity.in",
            },
        )
        assert resp.status_code in (200, 201)

        # Add a distinct Student 2 to Team 2
        resp = client.post(
            f"/api/v1/research/teams/{team2_id}/students",
            headers=auth_header(token),
            json={
                "full_name": "Priya Nair",
                "registration_number": "2140102",
                "email": "priya.nair@christuniversity.in",
                "programme": "B.Tech ECE",
                "semester": "Semester 6",
            },
        )
        assert resp.status_code == 201

        # Check centralized student directory deduplication
        resp = client.get("/api/v1/research/directory", headers=auth_header(token))
        assert resp.status_code == 200
        directory = resp.get_json()["data"]
        assert len(directory) == 2  # Only Rohan and Priya (no duplicate Rohan)

        rohan_entry = next(s for s in directory if s["registration_number"] == "2140101")
        assert len(rohan_entry["teams"]) == 2  # Belongs to both teams

    def test_04_project_milestone_task_workflow(self, client):
        """Test full project, milestone, task creation, and student assignment."""
        token, user = login_user(client, "eldho.paul", "Research2026!Eldho")

        # Create Team & Student
        resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(token),
            json={"name": "Vision AI Group", "domain": "Computer Vision"},
        )
        team_id = resp.get_json()["data"]["id"]

        resp = client.post(
            f"/api/v1/research/teams/{team_id}/students",
            headers=auth_header(token),
            json={
                "full_name": "Aditya Verma",
                "registration_number": "2140105",
                "email": "aditya.verma@christuniversity.in",
            },
        )
        student_id = resp.get_json()["data"]["student"]["id"]

        # Create Project
        resp = client.post(
            "/api/v1/research/projects",
            headers=auth_header(token),
            json={
                "team_id": team_id,
                "title": "Low-Latency Transformer Inference",
                "research_problem": "Quantization effects on real-time vision transformers.",
                "objectives": "Achieve <15ms latency with under 1% accuracy degradation.",
                "assigned_student_ids": [student_id],
                "start_date": "2026-11-01T00:00:00Z",
                "expected_completion_date": "2026-12-15T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        project = resp.get_json()["data"]
        project_id = project["id"]
        assert project["title"] == "Low-Latency Transformer Inference"

        # Create Milestone
        resp = client.post(
            f"/api/v1/research/projects/{project_id}/milestones",
            headers=auth_header(token),
            json={
                "title": "Phase 1: Literature Survey & Baseline",
                "description": "Survey 20 benchmark papers on transformer quantization.",
                "target_criteria": "Review 20 papers and benchmark ViT-Base on GPU.",
                "due_date": "2026-11-10T18:00:00Z",
                "priority": "high",
                "assigned_student_ids": [student_id],
            },
        )
        assert resp.status_code == 201
        milestone = resp.get_json()["data"]
        milestone_id = milestone["id"]

        # Create Task under Milestone
        resp = client.post(
            f"/api/v1/research/milestones/{milestone_id}/tasks",
            headers=auth_header(token),
            json={
                "title": "Review 20 Papers on INT8 Quantization",
                "instructions": "Extract model architecture, speedup, and top-1 accuracy.",
                "completion_criteria": "Spreadsheet with 20 papers and citation bibtex.",
                "priority": "high",
                "due_date": "2026-11-08T18:00:00Z",
                "assigned_student_ids": [student_id],
            },
        )
        assert resp.status_code == 201
        task = resp.get_json()["data"]
        assert task["status"] == "not_started"

    def test_05_student_progress_submission_and_two_way_feedback(self, client):
        """Test student submitting progress and faculty engaging in two-way continuous feedback."""
        fac_token, _ = login_user(client, "eldho.paul", "Research2026!Eldho")

        # Setup team, student, project, milestone, task
        t_resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(fac_token),
            json={"name": "Robotics Lab", "domain": "Control Systems"},
        )
        team_id = t_resp.get_json()["data"]["id"]

        st_resp = client.post(
            f"/api/v1/research/teams/{team_id}/students",
            headers=auth_header(fac_token),
            json={
                "full_name": "Rohan Sharma",
                "registration_number": "2140101",
                "email": "rohan.sharma@christuniversity.in",
            },
        )
        student_info = st_resp.get_json()["data"]
        student_id = student_info["student"]["id"]
        temp_pass = student_info.get("temporary_password", "ResPass2026!0101")

        p_resp = client.post(
            "/api/v1/research/projects",
            headers=auth_header(fac_token),
            json={"team_id": team_id, "title": "Autonomous Navigation", "assigned_student_ids": [student_id]},
        )
        project_id = p_resp.get_json()["data"]["id"]

        m_resp = client.post(
            f"/api/v1/research/projects/{project_id}/milestones",
            headers=auth_header(fac_token),
            json={"title": "Perception Module", "due_date": "2026-11-20T00:00:00Z"},
        )
        milestone_id = m_resp.get_json()["data"]["id"]

        task_resp = client.post(
            f"/api/v1/research/milestones/{milestone_id}/tasks",
            headers=auth_header(fac_token),
            json={"title": "LiDAR Point Cloud Filter", "assigned_student_ids": [student_id]},
        )
        task_id = task_resp.get_json()["data"]["id"]

        # Student logs in
        student_user = User.query.filter_by(role=User.ROLE_STUDENT_RESEARCHER).first()
        student_token, s_user = login_user(client, student_user.username, temp_pass)
        assert s_user["role"] == User.ROLE_STUDENT_RESEARCHER

        # Student views overview
        resp = client.get("/api/v1/research/student/overview", headers=auth_header(student_token))
        assert resp.status_code == 200
        overview = resp.get_json()["data"]
        assert len(overview["teams"]) >= 1
        assert len(overview["tasks"]) >= 1

        # Student submits progress
        resp = client.post(
            f"/api/v1/research/tasks/{task_id}/submissions",
            headers=auth_header(student_token),
            json={
                "work_completed_percentage": 60,
                "papers_reviewed_count": 12,
                "citations_count": 8,
                "notes": "Completed initial survey of 12 papers focusing on PTQ.",
                "challenges_faced": "Need access to two IEEE papers behind paywall.",
                "next_steps": "Review remaining 8 papers on QAT.",
            },
        )
        assert resp.status_code == 201
        submission = resp.get_json()["data"]
        assert submission["work_completed_percentage"] == 60

        # Faculty views continuous feedback thread
        resp = client.get(f"/api/v1/research/tasks/{task_id}/thread", headers=auth_header(fac_token))
        assert resp.status_code == 200
        thread_data = resp.get_json()["data"]
        assert thread_data["task_status"] == "submitted_for_review"
        assert len(thread_data["messages"]) >= 1

        # Faculty requests revision with notes
        resp = client.post(
            f"/api/v1/research/tasks/{task_id}/messages",
            headers=auth_header(fac_token),
            json={
                "message": "Good start Rohan. Please include recent 2025 CVPR papers on 4-bit weights.",
                "action": "request_revision",
            },
        )
        assert resp.status_code == 201

        # Verify task status is now revision_requested
        resp = client.get(f"/api/v1/research/tasks/{task_id}/thread", headers=auth_header(fac_token))
        assert resp.get_json()["data"]["task_status"] == "revision_requested"

        # Student responds to feedback
        resp = client.post(
            f"/api/v1/research/tasks/{task_id}/messages",
            headers=auth_header(student_token),
            json={
                "message": "Understood Professor. I have added 4 CVPR 2025 papers to the review table.",
                "action": "comment",
            },
        )
        assert resp.status_code == 201

        # Faculty approves
        resp = client.post(
            f"/api/v1/research/tasks/{task_id}/messages",
            headers=auth_header(fac_token),
            json={
                "message": "Excellent work. The literature review is comprehensive and approved.",
                "action": "approve",
            },
        )
        assert resp.status_code == 201

        # Verify final status
        resp = client.get(f"/api/v1/research/tasks/{task_id}/thread", headers=auth_header(fac_token))
        assert resp.get_json()["data"]["task_status"] == "approved"
        assert resp.get_json()["data"]["progress_percentage"] == 100

    def test_06_meeting_scheduler_and_attendance(self, client):
        """Test scheduling research meetings and recording attendance."""
        token, user = login_user(client, "eldho.paul", "Research2026!Eldho")

        # Create team & student
        t_resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(token),
            json={"name": "Signal Processing Lab", "domain": "DSP"},
        )
        team_id = t_resp.get_json()["data"]["id"]

        st_resp = client.post(
            f"/api/v1/research/teams/{team_id}/students",
            headers=auth_header(token),
            json={"full_name": "Sneha Sen", "registration_number": "2140108", "email": "sneha.sen@christuniversity.in"},
        )
        student_id = st_resp.get_json()["data"]["student"]["id"]

        # Schedule meeting
        resp = client.post(
            "/api/v1/research/meetings",
            headers=auth_header(token),
            json={
                "team_id": team_id,
                "title": "Weekly Research Progress Review",
                "agenda": "Review benchmark results and discuss hardware setup.",
                "meeting_datetime": "2026-11-05T14:30:00Z",
                "duration_minutes": 45,
                "location": "Research Lab 304, Academic Block 2",
                "meeting_link": "https://meet.google.com/res-eldho-dl",
                "participant_student_ids": [student_id],
            },
        )
        assert resp.status_code == 201
        meeting = resp.get_json()["data"]
        meeting_id = meeting["id"]
        assert meeting["title"] == "Weekly Research Progress Review"

        # Record attendance
        resp = client.post(
            f"/api/v1/research/meetings/{meeting_id}/attendance",
            headers=auth_header(token),
            json={
                "attendance": [
                    {"student_id": student_id, "attendance_status": "present", "attendance_notes": "Presented slides."}
                ],
                "notes": "Good progress shown on benchmark setup.",
            },
        )
        assert resp.status_code == 200
        updated = resp.get_json()["data"]
        assert updated["notes"] == "Good progress shown on benchmark setup."
        assert updated["participants"][0]["attendance_status"] == "present"

    def test_07_idor_and_permission_isolation(self, client):
        """Test that one faculty coordinator cannot access or modify another's research records."""
        # Dr Eldho creates a team
        eldho_token, _ = login_user(client, "eldho.paul", "Research2026!Eldho")
        resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(eldho_token),
            json={"name": "Dr Eldho Private Team", "domain": "Confidential AI"},
        )
        eldho_team_id = resp.get_json()["data"]["id"]

        # Dr Ambily Babu attempts to access Dr Eldho's team
        ambily_token, _ = login_user(client, "ambily.babu", "Research2026!Ambily")

        # Dr Ambily attempts to read Dr Eldho's team details -> 403 Forbidden
        resp = client.get(f"/api/v1/research/teams/{eldho_team_id}", headers=auth_header(ambily_token))
        assert resp.status_code == 403

        # Dr Ambily attempts to add student to Dr Eldho's team -> 403 Forbidden
        resp = client.post(
            f"/api/v1/research/teams/{eldho_team_id}/students",
            headers=auth_header(ambily_token),
            json={"full_name": "Unauthorized Student", "registration_number": "9999999", "email": "unauth@christ.in"},
        )
        assert resp.status_code == 403

        # Student attempts to create a research team -> 403 Forbidden
        st_resp = client.post(
            f"/api/v1/research/teams/{eldho_team_id}/students",
            headers=auth_header(eldho_token),
            json={"full_name": "Rahul Verma", "registration_number": "2140109", "email": "rahul.v@christuniversity.in"},
        )
        student_info = st_resp.get_json()["data"]
        student_user = User.query.filter_by(email="rahul.v@christuniversity.in").first()
        student_token, _ = login_user(client, student_user.username, student_info["temporary_password"])

        resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(student_token),
            json={"name": "Hacked Team", "domain": "Hacking"},
        )
        assert resp.status_code == 403

    def test_08_password_management_workflows(self, client):
        """
        Test complete password management requirements:
        1. Faculty can change own password at any time.
        2. Faculty assigns a password when adding a student.
        3. Student logs in with faculty-assigned password.
        4. Student changes password anytime in student portal.
        5. Faculty can set/reset student password.
        6. Unauthorized faculty cannot reset other students' passwords.
        """
        # 1. Faculty changes own password anytime
        fac_token, fac_user = login_user(client, "chidambaram.s", "Research2026!Chidambaram")

        # First change (e.g. from initial)
        resp = client.post(
            "/api/v1/research/auth/change-password",
            headers=auth_header(fac_token),
            json={
                "current_password": "Research2026!Chidambaram",
                "new_password": "ChidambaramCustomPass2026!A",
            },
        )
        assert resp.status_code == 200

        # Faculty changes password AGAIN according to will
        resp = client.post(
            "/api/v1/research/auth/change-password",
            headers=auth_header(fac_token),
            json={
                "current_password": "ChidambaramCustomPass2026!A",
                "new_password": "ChidambaramCustomPass2026!B",
            },
        )
        assert resp.status_code == 200

        # Verify login with the latest password
        new_fac_token, _ = login_user(client, "chidambaram.s", "ChidambaramCustomPass2026!B")
        assert new_fac_token is not None

        # 2. Faculty creates a team and adds student with assigned password
        team_resp = client.post(
            "/api/v1/research/teams",
            headers=auth_header(new_fac_token),
            json={"name": "VLSI Team", "domain": "Semiconductors"},
        )
        team_id = team_resp.get_json()["data"]["id"]

        add_resp = client.post(
            f"/api/v1/research/teams/{team_id}/students",
            headers=auth_header(new_fac_token),
            json={
                "full_name": "Meera Nair",
                "registration_number": "2140555",
                "email": "meera.nair@christuniversity.in",
                "password": "FacultyGivenPass2026!",
            },
        )
        assert add_resp.status_code == 201
        st_data = add_resp.get_json()["data"]
        student_id = st_data["student"]["id"]
        student_username = st_data["username"]
        assert st_data["password"] == "FacultyGivenPass2026!"

        # 3. Student logs in directly with faculty-assigned password
        st_token, st_user = login_user(client, student_username, "FacultyGivenPass2026!")
        assert st_token is not None
        assert st_user["role"] == "student_researcher"

        # 4. Student changes password anytime in student portal
        st_change_resp = client.post(
            "/api/v1/research/auth/change-password",
            headers=auth_header(st_token),
            json={
                "current_password": "FacultyGivenPass2026!",
                "new_password": "MeeraOwnChosenPass2026!",
            },
        )
        assert st_change_resp.status_code == 200

        # Verify student can log in with new password
        new_st_token, _ = login_user(client, student_username, "MeeraOwnChosenPass2026!")
        assert new_st_token is not None

        # 5. Faculty resets/sets student password
        reset_resp = client.post(
            f"/api/v1/research/students/{student_id}/password",
            headers=auth_header(new_fac_token),
            json={"new_password": "ResetByProfPrabhu2026!"},
        )
        assert reset_resp.status_code == 200

        # Verify student can log in with the reset password
        after_reset_token, _ = login_user(client, student_username, "ResetByProfPrabhu2026!")
        assert after_reset_token is not None

        # 6. IDOR: Another faculty cannot reset this student's password
        other_fac_token, _ = login_user(client, "eldho.paul", "Research2026!Eldho")
        unauth_reset = client.post(
            f"/api/v1/research/students/{student_id}/password",
            headers=auth_header(other_fac_token),
            json={"new_password": "HackerPass123!"},
        )
        assert unauth_reset.status_code == 403
