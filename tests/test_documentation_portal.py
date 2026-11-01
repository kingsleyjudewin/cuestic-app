import pytest
import io
from app.extensions import db
from app.models.user import User
from app.models.member import Member
from app.models.documentation import EventFolder, FolderDocument
from tests.conftest import create_user_with_token


@pytest.fixture
def doc_member_user(app, seed_teams):
    """Fixture providing an authenticated Documentation team member."""
    user, token = create_user_with_token("surasmita_test", User.ROLE_MEMBER, "surasmita_test@test.edu")
    doc_team = seed_teams["documentation"]
    member = Member(
        full_name="Surasmita",
        registration_number="REG-DOC-001",
        class_name="6BTELCS",
        phone_number="+918078156512",
        team_id=doc_team.id,
        linked_user_id=user.id,
        is_active=True,
    )
    db.session.add(member)
    db.session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "token": token, "headers": headers, "member": member, "team": doc_team}


@pytest.fixture
def volunteer_member_user(app, seed_teams):
    """Fixture providing an authenticated Volunteering team member."""
    user, token = create_user_with_token("vol_test", User.ROLE_MEMBER, "vol_test@test.edu")
    vol_team = seed_teams["volunteering"]
    member = Member(
        full_name="Volunteer Person",
        registration_number="REG-VOL-001",
        class_name="6BTEC",
        phone_number="+919000000001",
        team_id=vol_team.id,
        linked_user_id=user.id,
        is_active=True,
    )
    db.session.add(member)
    db.session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "token": token, "headers": headers, "member": member, "team": vol_team}


def test_documentation_folder_crud(client, doc_member_user):
    """Test folder creation, listing, retrieval, and deletion for Documentation member."""
    headers = doc_member_user["headers"]

    # 1. Create event folder
    res_create = client.post(
        "/api/v1/documentation/folders",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "name": "MAGNOVITE 2026 Documentation",
            "description": "All photos, attendance lists, and official reports.",
            "event_date": "2026-11-05T10:00:00Z",
        }
    )
    assert res_create.status_code == 201
    folder = res_create.get_json()["data"]
    folder_id = folder["id"]
    assert folder["name"] == "MAGNOVITE 2026 Documentation"
    assert folder["document_count"] == 0

    # 2. List folders
    res_list = client.get("/api/v1/documentation/folders", headers=headers)
    assert res_list.status_code == 200
    folders = res_list.get_json()["data"]
    assert len(folders) >= 1
    assert any(f["id"] == folder_id for f in folders)

    # 3. Get folder by ID
    res_get = client.get(f"/api/v1/documentation/folders/{folder_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.get_json()["data"]["id"] == folder_id
    assert "documents" in res_get.get_json()["data"]

    # 4. Delete folder
    res_del = client.delete(f"/api/v1/documentation/folders/{folder_id}", headers=headers)
    assert res_del.status_code == 200

    # 5. Verify deleted
    res_get2 = client.get(f"/api/v1/documentation/folders/{folder_id}", headers=headers)
    assert res_get2.status_code == 404


def test_document_upload_and_download(client, doc_member_user):
    """Test uploading a file to an event folder, downloading it, and deleting it."""
    headers = doc_member_user["headers"]

    # Create folder first
    res_f = client.post(
        "/api/v1/documentation/folders",
        headers={**headers, "Content-Type": "application/json"},
        json={"name": "Tech Talk 2026"}
    )
    folder_id = res_f.get_json()["data"]["id"]

    # Upload a sample document
    fake_content = b"Activity report documentation notes and agenda."
    data = {
        "file": (io.BytesIO(fake_content), "agenda.docx")
    }
    res_up = client.post(
        f"/api/v1/documentation/folders/{folder_id}/documents",
        headers=headers,
        content_type="multipart/form-data",
        data=data
    )
    assert res_up.status_code == 201
    doc_info = res_up.get_json()["data"]
    doc_id = doc_info["id"]
    assert doc_info["original_filename"] == "agenda.docx"
    assert doc_info["file_size"] == len(fake_content)

    # Download file
    res_down = client.get(f"/api/v1/documentation/documents/{doc_id}/download", headers=headers)
    assert res_down.status_code == 200
    assert res_down.data == fake_content

    # Delete file
    res_del = client.delete(f"/api/v1/documentation/documents/{doc_id}", headers=headers)
    assert res_del.status_code == 200

    # Verify deleted
    res_down2 = client.get(f"/api/v1/documentation/documents/{doc_id}/download", headers=headers)
    assert res_down2.status_code == 404


def test_unauthorized_team_member_access_blocked(client, volunteer_member_user, doc_member_user):
    """Verify that a member of another team (Volunteering) cannot access Documentation portal resources."""
    vol_headers = volunteer_member_user["headers"]
    doc_headers = doc_member_user["headers"]

    # Doc member creates folder
    res_f = client.post(
        "/api/v1/documentation/folders",
        headers={**doc_headers, "Content-Type": "application/json"},
        json={"name": "Confidential Documentation"}
    )
    folder_id = res_f.get_json()["data"]["id"]

    # Volunteer attempts to list documentation folders -> 403 Forbidden
    res_list = client.get("/api/v1/documentation/folders", headers=vol_headers)
    assert res_list.status_code == 403

    # Volunteer attempts to view specific folder -> 403 Forbidden
    res_view = client.get(f"/api/v1/documentation/folders/{folder_id}", headers=vol_headers)
    assert res_view.status_code == 403

    # Volunteer attempts to upload to folder -> 403 Forbidden
    res_up = client.post(
        f"/api/v1/documentation/folders/{folder_id}/documents",
        headers=vol_headers,
        content_type="multipart/form-data",
        data={"file": (io.BytesIO(b"hack"), "hack.docx")}
    )
    assert res_up.status_code == 403


def test_president_has_administrative_access(client, admin_user, doc_member_user):
    """Verify President/Admin retains full administrative access to Documentation resources."""
    admin_headers = admin_user["headers"]
    doc_headers = doc_member_user["headers"]

    # Doc member creates folder
    res_f = client.post(
        "/api/v1/documentation/folders",
        headers={**doc_headers, "Content-Type": "application/json"},
        json={"name": "Symposium Documentation"}
    )
    folder_id = res_f.get_json()["data"]["id"]

    # Admin lists folders
    res_list = client.get("/api/v1/documentation/folders", headers=admin_headers)
    assert res_list.status_code == 200
    assert any(f["id"] == folder_id for f in res_list.get_json()["data"])
