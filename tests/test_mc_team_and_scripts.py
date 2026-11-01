import os
import pytest
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.event import Event
from app.models.task import Task
from app.models.member import Member
from app.models.mc_script import McScript, McScriptReview
from app.services.mc_script_service import McScriptService
from app.services.mc_ai_service import MCAssistantService
from app.utils.errors import PermissionDeniedError, NotFoundError, ValidationError
from tests.conftest import create_user_with_token


def test_mc_team_get_or_create(app):
    """Verify that McScriptService retrieves or creates the MC Team without error."""
    with app.app_context():
        team = McScriptService.get_or_create_mc_team()
        assert team is not None
        assert team.slug == "mc"
        assert "MC" in team.name

        # Calling again should return the same team
        team2 = McScriptService.get_or_create_mc_team()
        assert team2.id == team.id


def test_mc_script_lifecycle_and_review(app, admin_user, member_user):
    """Test full script lifecycle: create draft, update, submit, and review."""
    with app.app_context():
        admin = User.query.filter_by(username="test_admin").first()
        member = User.query.filter_by(username="test_member").first()

        # 1. Member creates a draft script
        script_data = {
            "title": "Inauguration Ceremony 2026",
            "event_type": "Inauguration",
            "venue": "Main Auditorium",
            "tone": "Formal",
            "number_of_anchors": 2,
            "anchors": [
                {"id": 1, "name": "Anchor 1 (Host)", "role": "Lead Host"},
                {"id": 2, "name": "Anchor 2 (Co-Host)", "role": "Co-Host"},
            ],
            "chief_guest_details": "Dr. A. P. Sharma, Director",
            "segments": [
                {
                    "id": "1",
                    "title": "Welcome Address",
                    "anchor": "Anchor 1 (Host)",
                    "stage_direction": "[Step forward, smile]",
                    "dialogue": "A warm welcome to everyone gathered here.",
                }
            ],
        }

        script = McScriptService.create_script(script_data, member)
        assert script.id is not None
        assert script.status == McScript.STATUS_DRAFT
        assert script.created_by == member.id
        assert len(script.get_segments()) == 1

        # 2. Member updates the draft
        updated_data = {
            "title": "Grand Inauguration Ceremony 2026",
            "duration": "1.5 Hours",
        }
        script = McScriptService.update_script(script.id, updated_data, member)
        assert script.title == "Grand Inauguration Ceremony 2026"
        assert script.duration == "1.5 Hours"

        # 3. Member submits for review
        script = McScriptService.submit_for_review(script.id, member)
        assert script.status == McScript.STATUS_SUBMITTED

        # 4. Ordinary member cannot approve their own script
        with pytest.raises(PermissionDeniedError):
            McScriptService.review_script(script.id, "approved", "Self approval", member)

        # 5. Admin / MC Lead approves script
        script = McScriptService.review_script(script.id, "approved", "Well structured hosting flow", admin)
        assert script.status == McScript.STATUS_APPROVED

        # Verify review record
        reviews = McScriptReview.query.filter_by(script_id=script.id).all()
        assert len(reviews) == 1
        assert reviews[0].decision == "approved"
        assert reviews[0].reviewer_id == admin.id


def test_mc_script_revision_workflow(app, admin_user, member_user):
    """Test revision requested workflow and re-submission."""
    with app.app_context():
        admin = User.query.filter_by(username="test_admin").first()
        member = User.query.filter_by(username="test_member").first()

        script = McScriptService.create_script(
            {"title": "Tech Talk Script", "venue": "Seminar Hall"},
            member,
        )
        McScriptService.submit_for_review(script.id, member)

        # Admin requests revision
        script = McScriptService.review_script(script.id, "revision_requested", "Please add vote of thanks", admin)
        assert script.status == McScript.STATUS_REVISION_REQUESTED

        # Member updates script
        script = McScriptService.update_script(script.id, {"title": "Tech Talk Script with Thanks"}, member)
        assert script.status == McScript.STATUS_IN_PROGRESS

        # Re-submit
        script = McScriptService.submit_for_review(script.id, member)
        assert script.status == McScript.STATUS_SUBMITTED


def test_mc_script_docx_generation(app, admin_user):
    """Test generating formatted .docx file from script segments."""
    with app.app_context():
        admin = User.query.filter_by(username="test_admin").first()

        script = McScriptService.create_script(
            {
                "title": "Department Symposium Script",
                "venue": "Campus Amphitheatre",
                "tone": "Energetic",
                "chief_guest_details": "Prof. Rao",
                "segments": [
                    {
                        "id": "1",
                        "title": "Opening Fanfare",
                        "anchor": "Anchor 1",
                        "stage_direction": "[Upbeat music fades out, spot on Anchor 1]",
                        "dialogue": "Welcome to the grand Department Symposium!",
                    },
                    {
                        "id": "2",
                        "title": "Welcome Dignitaries",
                        "anchor": "Anchor 2",
                        "stage_direction": "[Turn to VIP row]",
                        "dialogue": "We are honored to have Prof. Rao with us.",
                    },
                ],
            },
            admin,
        )

        out_path, filename = McScriptService.generate_docx(script.id, admin)
        assert os.path.exists(out_path)
        assert filename.endswith(".docx")
        assert os.path.getsize(out_path) > 0

        # Clean up generated file after test
        if os.path.exists(out_path):
            os.remove(out_path)


def test_mc_api_endpoints(client, admin_user, member_user):
    """Test API v1 MC endpoints via Flask test client."""
    admin_token = admin_user["token"]
    member_token = member_user["token"]
    # 1. Get dashboard summary
    resp = client.get("/api/v1/mc/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "assigned_events_count" in data
    assert "scripts_in_progress" in data
    assert "upcoming_events" in data

    # 2. Create script via POST
    create_payload = {
        "title": "API Test Hosting Script",
        "venue": "Room 401",
        "tone": "Formal",
        "number_of_anchors": 2,
        "segments": [
            {
                "id": "1",
                "title": "Welcome",
                "anchor": "Anchor 1",
                "dialogue": "Good morning audience.",
            }
        ],
    }
    resp = client.post(
        "/api/v1/mc/scripts",
        json=create_payload,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 201
    script_id = resp.get_json()["data"]["id"]

    # 3. Retrieve script via GET
    resp = client.get(
        f"/api/v1/mc/scripts/{script_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "API Test Hosting Script"

    # 4. Generate DOCX
    resp = client.post(
        f"/api/v1/mc/scripts/{script_id}/generate-docx",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "generated"

    # 5. Download DOCX
    resp = client.get(
        f"/api/v1/mc/scripts/{script_id}/download-docx",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats" in resp.content_type


def test_mc_assistant_service_formatting(app, monkeypatch):
    """Test AI assistant formatting without external network calls."""
    sample_response = '''{
      "title": "Hackathon 2026 - MC Script",
      "segments": [
        {
          "id": "1",
          "title": "Welcome Address",
          "anchor": "Anchor 1",
          "stage_direction": "[Step to microphone, smile]",
          "dialogue": "Welcome hackers to the national department hackathon!"
        },
        {
          "id": "2",
          "title": "Rules Announcement",
          "anchor": "Anchor 2",
          "stage_direction": "[Display slide 2]",
          "dialogue": "The 24 hour coding countdown begins now."
        }
      ]
    }'''

    def mock_generate(*args, **kwargs):
        return sample_response, "gemini", "gemini-3.5-flash"

    monkeypatch.setattr(
        "app.services.ai_service.AIService.generate_with_resilient_fallback",
        mock_generate,
    )

    with app.app_context():
        event_info = {
            "title": "Hackathon 2026",
            "venue": "Innovation Lab",
            "number_of_anchors": 2,
            "anchors": [{"name": "Anchor 1"}, {"name": "Anchor 2"}],
        }
        res = MCAssistantService.generate_full_script(event_info)
        assert res["title"] == "Hackathon 2026 - MC Script"
        assert len(res["segments"]) >= 2
        assert "hackathon" in res["full_script"].lower()


def test_mc_permissions_and_deletion(app, admin_user, member_user):
    """Verify script delete permissions."""
    with app.app_context():
        admin = User.query.filter_by(username="test_admin").first()
        member1 = User.query.filter_by(username="test_member").first()

        # Create another member
        member2 = User(username="test_member_two", email="mem2@test.edu", role=User.ROLE_MEMBER, is_active=True)
        member2.set_password("Pass123!")
        db.session.add(member2)
        db.session.commit()

        script = McScriptService.create_script({"title": "Member 1 Private Script"}, member1)

        # Member 2 cannot delete Member 1's script
        with pytest.raises(PermissionDeniedError):
            McScriptService.delete_script(script.id, member2)

        # Admin CAN delete
        assert McScriptService.delete_script(script.id, admin) is True


def test_mc_folders_and_uploads(app, admin_user, client):
    """Test MC folder creation, script file uploading, and team members listing."""
    token = admin_user["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create MC folder
    res = client.post("/api/v1/mc/folders", json={"name": "Annual Day 2026", "description": "Hosting scripts"}, headers=headers)
    assert res.status_code == 201
    folder_id = res.get_json()["data"]["id"]

    # 2. List folders
    res = client.get("/api/v1/mc/folders", headers=headers)
    assert res.status_code == 200
    assert any(f["id"] == folder_id for f in res.get_json()["data"])

    # 3. Upload script file to folder
    import io
    fake_file = (io.BytesIO(b"Anchor 1: Welcome!\nAnchor 2: Good evening!"), "script_v1.txt")
    res = client.post(
        f"/api/v1/mc/folders/{folder_id}/upload",
        data={"file": fake_file},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert res.status_code == 201
    doc_id = res.get_json()["data"]["document"]["id"]

    # 4. Get folder details
    res = client.get(f"/api/v1/mc/folders/{folder_id}", headers=headers)
    assert res.status_code == 200
    fdata = res.get_json()["data"]
    assert len(fdata["documents"]) >= 1

    # 5. Download document
    res = client.get(f"/api/v1/mc/documents/{doc_id}/download", headers=headers)
    assert res.status_code == 200
    assert b"Welcome" in res.data

    # 6. Team members endpoint
    res = client.get("/api/v1/mc/team-members", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.get_json()["data"], list)

    # 7. Delete folder
    res = client.delete(f"/api/v1/mc/folders/{folder_id}", headers=headers)
    assert res.status_code == 200

