import io
import json
from unittest.mock import patch
import pytest
from PIL import Image
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.models.documentation import EventFolder
from app.models.media import MediaFile, GoogleDriveIntegration
from app.services.auth_service import AuthService
from tests.conftest import create_user_with_token


@pytest.fixture
def media_setup(app):
    """Setup teams, users, and member records for media tests."""
    with app.app_context():
        # 1. Teams
        t_vol = Team(id=1, name="Volunteering", slug="volunteering")
        t_doc = Team(id=2, name="Documentation", slug="documentation")
        t_med = Team(id=3, name="Media", slug="media")
        db.session.add_all([t_vol, t_doc, t_med])
        db.session.commit()

        # 2. Admin
        admin = User(username="admin", email="admin@test.edu", role="president", is_active=True)
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()
        admin_login = AuthService.login("admin", "AdminPass123!")

        # 3. Media Member (Arpitha CU)
        media_user = User(
            username="arpitha.cu",
            email="arpitha.cu@gmail.com",
            role="member",
            is_active=True,
            credential_setup_status="completed"
        )
        media_user.set_password("MediaPass123!")
        db.session.add(media_user)
        db.session.commit()

        media_member = Member(
            full_name="Arpitha CU",
            class_name="6BTELCS",
            phone_number="+917736083222",
            team_id=3,
            linked_user_id=media_user.id,
            is_active=True
        )
        db.session.add(media_member)
        db.session.commit()
        media_login = AuthService.login("arpitha.cu", "MediaPass123!")

        # 4. Volunteering Member (Sagar CU)
        vol_user = User(
            username="sagar.cu",
            email="sagar.cu@gmail.com",
            role="member",
            is_active=True,
            credential_setup_status="completed"
        )
        vol_user.set_password("VolunteerPass123!")
        db.session.add(vol_user)
        db.session.commit()

        vol_member = Member(
            full_name="Sagar CU",
            class_name="6BTEC",
            phone_number="+919999988888",
            team_id=1,
            linked_user_id=vol_user.id,
            is_active=True
        )
        db.session.add(vol_member)
        db.session.commit()
        vol_login = AuthService.login("sagar.cu", "VolunteerPass123!")

        return {
            "admin_token": admin_login["token"],
            "media_token": media_login["token"],
            "vol_token": vol_login["token"],
            "media_user_id": media_user.id,
        }


def create_test_image(color="blue", with_gps=False) -> io.BytesIO:
    """Generate image bytes for upload testing, optionally embedding GPS EXIF metadata."""
    img = Image.new("RGB", (100, 100), color=color)
    buf = io.BytesIO()
    if with_gps:
        exif = img.getexif()
        gps_ifd = exif.get_ifd(0x8825)
        # 12° 58' 23.4" N, 77° 35' 45.6" E (Bangalore)
        gps_ifd[1] = "N"
        gps_ifd[2] = (12, 58, 23.4)
        gps_ifd[3] = "E"
        gps_ifd[4] = (77, 35, 45.6)
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_media_folder_crud(client, media_setup):
    """Test creating, listing, reading, and deleting Media event folders."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    # 1. Create Folder
    res = client.post("/api/v1/media/folders", json={
        "name": "Tech Expo 2026",
        "description": "Annual Technology Exhibition Coverage",
        "event_date": "2026-11-20T10:00:00Z"
    }, headers=headers)
    assert res.status_code == 201
    folder_data = res.get_json()["data"]
    folder_id = folder_data["id"]
    assert folder_data["name"] == "Tech Expo 2026"
    assert folder_data["team_id"] == 3
    assert folder_data["document_count"] == 0
    assert folder_data["media_count"] == 0

    # 2. List Folders
    list_res = client.get("/api/v1/media/folders", headers=headers)
    assert list_res.status_code == 200
    folders = list_res.get_json()["data"]
    assert len(folders) >= 1
    assert any(f["id"] == folder_id for f in folders)

    # 3. Search Folders
    search_res = client.get("/api/v1/media/folders?q=Tech+Expo", headers=headers)
    assert search_res.status_code == 200
    assert len(search_res.get_json()["data"]) >= 1

    # 4. Get Folder Details
    get_res = client.get(f"/api/v1/media/folders/{folder_id}?include_media=true", headers=headers)
    assert get_res.status_code == 200
    data = get_res.get_json()["data"]
    assert data["name"] == "Tech Expo 2026"
    assert "media_files" in data

    # 5. Delete Folder
    del_res = client.delete(f"/api/v1/media/folders/{folder_id}", headers=headers)
    assert del_res.status_code == 200
    assert client.get(f"/api/v1/media/folders/{folder_id}", headers=headers).status_code == 404


def test_media_authorization_barriers(client, media_setup):
    """Ensure non-media users (Volunteers, Documentation, unauthenticated) are blocked."""
    vol_headers = {"Authorization": f"Bearer {media_setup['vol_token']}"}
    admin_headers = {"Authorization": f"Bearer {media_setup['admin_token']}"}

    # Unauthenticated request
    unauth_res = client.get("/api/v1/media/folders")
    assert unauth_res.status_code == 401

    # Volunteer trying to access Media workspace
    vol_res = client.get("/api/v1/media/folders", headers=vol_headers)
    assert vol_res.status_code == 403
    assert "FORBIDDEN" in vol_res.get_json()["error"]["code"]

    vol_create = client.post("/api/v1/media/folders", json={"name": "Hacked Folder"}, headers=vol_headers)
    assert vol_create.status_code == 403

    # Admin/President has administrative access
    admin_res = client.get("/api/v1/media/folders", headers=admin_headers)
    assert admin_res.status_code == 200


def test_media_upload_ordinary_and_geotagged_photos(client, media_setup):
    """Test uploading ordinary photos vs geotagged photos with EXIF extraction."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    # Create folder
    f_res = client.post("/api/v1/media/folders", json={"name": "Science Day"}, headers=headers)
    folder_id = f_res.get_json()["data"]["id"]

    # 1. Upload Normal Photo (no GPS)
    normal_buf = create_test_image(color="yellow", with_gps=False)
    up_res1 = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={
            "file": (normal_buf, "keynote_speaker.jpg"),
            "category": "photos",
            "destination": "firebase"
        },
        content_type="multipart/form-data",
        headers=headers
    )
    assert up_res1.status_code == 201
    file1 = up_res1.get_json()["data"]
    assert file1["category"] == "photos"
    assert file1["has_gps"] is False
    assert file1["gps_latitude"] is None
    assert file1["storage_provider"] in ("firebase", "local")

    # 2. Upload Geotagged Photo (with GPS EXIF)
    geo_buf = create_test_image(color="green", with_gps=True)
    up_res2 = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={
            "file": (geo_buf, "outdoor_crowd_geo.jpg"),
            "category": "geotagged_photos",
            "destination": "firebase"
        },
        content_type="multipart/form-data",
        headers=headers
    )
    assert up_res2.status_code == 201
    file2 = up_res2.get_json()["data"]
    assert file2["category"] == "geotagged_photos"
    assert file2["has_gps"] is True
    assert file2["gps_latitude"] == 12.973167
    assert file2["gps_longitude"] == 77.596
    assert file2["maps_url"] == "https://maps.google.com/?q=12.973167,77.596"

    # Verify counts in folder
    f_check = client.get(f"/api/v1/media/folders/{folder_id}", headers=headers).get_json()["data"]
    assert f_check["photos_count"] == 1
    assert f_check["geotagged_count"] == 1
    assert f_check["media_count"] == 2


def test_media_upload_videos_and_posters(client, media_setup):
    """Test uploading videos, posters, and validating rejection of bad formats/sizes."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    f_res = client.post("/api/v1/media/folders", json={"name": "Cultural Fest"}, headers=headers)
    folder_id = f_res.get_json()["data"]["id"]

    # 1. Video upload (.mp4)
    fake_video = io.BytesIO(b"fake mp4 video stream bytes")
    up_vid = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={"file": (fake_video, "stage_performance.mp4"), "category": "videos"},
        content_type="multipart/form-data",
        headers=headers
    )
    assert up_vid.status_code == 201
    assert up_vid.get_json()["data"]["category"] == "videos"

    # 2. Poster upload (.pdf / .png)
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake poster brochure content")
    up_post = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={"file": (fake_pdf, "event_banner.pdf"), "category": "posters"},
        content_type="multipart/form-data",
        headers=headers
    )
    assert up_post.status_code == 201
    assert up_post.get_json()["data"]["category"] == "posters"

    # 3. Reject invalid category
    bad_cat = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={"file": (io.BytesIO(b"data"), "file.jpg"), "category": "invalid_cat"},
        content_type="multipart/form-data",
        headers=headers
    )
    assert bad_cat.status_code == 400

    # 4. Reject disallowed extension (e.g. .exe or .py in photos)
    bad_ext = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={"file": (io.BytesIO(b"malicious script"), "script.exe"), "category": "photos"},
        content_type="multipart/form-data",
        headers=headers
    )
    assert bad_ext.status_code == 400


def test_media_file_download_and_deletion(client, media_setup):
    """Test downloading binary file and deleting it from storage and database."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    f_res = client.post("/api/v1/media/folders", json={"name": "Robotics Championship"}, headers=headers)
    folder_id = f_res.get_json()["data"]["id"]

    img_buf = create_test_image(color="cyan")
    up_res = client.post(
        f"/api/v1/media/folders/{folder_id}/upload",
        data={"file": (img_buf, "robot_prototype.jpg"), "category": "photos"},
        content_type="multipart/form-data",
        headers=headers
    )
    file_id = up_res.get_json()["data"]["id"]

    # Download file
    down_res = client.get(f"/api/v1/media/files/{file_id}/download", headers=headers)
    assert down_res.status_code == 200
    assert len(down_res.data) > 0

    # Delete file
    del_res = client.delete(f"/api/v1/media/files/{file_id}", headers=headers)
    assert del_res.status_code == 200

    # Confirm gone
    assert client.get(f"/api/v1/media/files/{file_id}", headers=headers).status_code == 404


def test_google_drive_folder_and_file_linking(client, media_setup):
    """Test linking an existing Google Drive folder and files without copying bytes to Firebase."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    f_res = client.post("/api/v1/media/folders", json={"name": "Convocation 2026"}, headers=headers)
    folder_id = f_res.get_json()["data"]["id"]

    # 1. Link Google Drive Folder
    link_res = client.post(
        f"/api/v1/media/folders/{folder_id}/link-drive",
        json={
            "drive_folder_id": "drive_folder_convocation_xyz123",
            "drive_folder_name": "Convocation 2026 High-Res Photos",
            "web_view_link": "https://drive.google.com/drive/folders/drive_folder_convocation_xyz123"
        },
        headers=headers
    )
    assert link_res.status_code == 200
    folder_data = link_res.get_json()["data"]
    assert folder_data["linked_drive_folder_id"] == "drive_folder_convocation_xyz123"
    assert folder_data["storage_source"] == "google_drive"

    # 2. Link a Google Drive File (mocking Drive API get_file_metadata)
    mock_drive_meta = {
        "id": "drive_file_keynote_999",
        "name": "Keynote_4K_Raw.mp4",
        "mime_type": "video/mp4",
        "file_size": 850000000,
        "web_view_link": "https://drive.google.com/file/d/drive_file_keynote_999/view",
        "thumbnail_link": "https://drive.google.com/thumbnail/999",
    }

    with patch("app.services.google_drive_service.GoogleDriveService.get_file_metadata", return_value=mock_drive_meta):
        file_link_res = client.post(
            f"/api/v1/media/folders/{folder_id}/link-drive-file",
            json={"drive_file_id": "drive_file_keynote_999"},
            headers=headers
        )
        assert file_link_res.status_code == 201
        linked_file = file_link_res.get_json()["data"]
        assert linked_file["storage_provider"] == "google_drive"
        assert linked_file["drive_file_id"] == "drive_file_keynote_999"
        assert linked_file["drive_web_view_link"] == "https://drive.google.com/file/d/drive_file_keynote_999/view"
        assert linked_file["category"] == "videos"
        file_id = linked_file["id"]

    # 3. Download Drive file redirects to web_view_link
    down_redirect = client.get(f"/api/v1/media/files/{file_id}/download", headers=headers)
    assert down_redirect.status_code == 302
    assert down_redirect.headers["Location"] == "https://drive.google.com/file/d/drive_file_keynote_999/view"

    # 4. Unlink Drive file removes database record only (does not delete from Google Drive)
    unlink_file_res = client.delete(f"/api/v1/media/files/{file_id}", headers=headers)
    assert unlink_file_res.status_code == 200
    assert client.get(f"/api/v1/media/files/{file_id}", headers=headers).status_code == 404

    # 5. Unlink Google Drive Folder
    unlink_folder_res = client.post(f"/api/v1/media/folders/{folder_id}/unlink-drive", headers=headers)
    assert unlink_folder_res.status_code == 200
    assert unlink_folder_res.get_json()["data"]["linked_drive_folder_id"] is None


def test_google_drive_status_and_disconnect(client, media_setup):
    """Test Google Drive status checking, disconnect, and OAuth error handling."""
    headers = {"Authorization": f"Bearer {media_setup['media_token']}"}

    # 1. Drive status when disconnected
    status_res = client.get("/api/v1/media/drive/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.get_json()["data"]["is_connected"] is False

    # 2. Auth URL when unconfigured raises clear message
    with patch("app.services.google_drive_service.GoogleDriveService.is_configured", return_value=False):
        url_res = client.get("/api/v1/media/drive/auth-url", headers=headers)
        assert url_res.status_code == 400
        assert "not yet configured" in url_res.get_json()["error"]["message"]

    # 3. Disconnect when not connected succeeds gracefully
    disc_res = client.post("/api/v1/media/drive/disconnect", headers=headers)
    assert disc_res.status_code == 200
