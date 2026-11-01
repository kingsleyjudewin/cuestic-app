import os
import io
import docx
import pytest
from unittest.mock import patch
from app.extensions import db
from app.models.user import User
from app.models.member import Member
from app.models.documentation import ActivityReport, EventFolder, FolderDocument
from tests.conftest import create_user_with_token


@pytest.fixture
def doc_setup(app, seed_teams):
    """Fixture providing authenticated Doc member, Volunteer member, and President."""
    doc_team = seed_teams["documentation"]
    vol_team = seed_teams["volunteering"]

    doc_user, doc_token = create_user_with_token("surasmita_rep_test", User.ROLE_MEMBER, "surasmita_rep@test.edu")
    doc_member = Member(
        full_name="Surasmita Report Tester",
        registration_number="REG-REP-001",
        class_name="6BTELCS",
        phone_number="+918078156512",
        team_id=doc_team.id,
        linked_user_id=doc_user.id,
        is_active=True,
    )
    db.session.add(doc_member)

    vol_user, vol_token = create_user_with_token("vol_rep_test", User.ROLE_MEMBER, "vol_rep@test.edu")
    vol_member = Member(
        full_name="Volunteer Tester",
        registration_number="REG-VOL-001",
        class_name="6BTEC",
        phone_number="+919008762143",
        team_id=vol_team.id,
        linked_user_id=vol_user.id,
        is_active=True,
    )
    db.session.add(vol_member)

    pres_user, pres_token = create_user_with_token("pres_rep_test", User.ROLE_PRESIDENT, "pres_rep@test.edu")
    db.session.commit()

    return {
        "doc_user": doc_user,
        "doc_token": doc_token,
        "vol_user": vol_user,
        "vol_token": vol_token,
        "pres_user": pres_user,
        "pres_token": pres_token,
        "doc_team": doc_team,
    }


def test_report_draft_lifecycle(client, doc_setup):
    headers = {"Authorization": f"Bearer {doc_setup['doc_token']}"}

    # 1. Create Report Draft
    payload = {
        "title": "Quantum AI Workshop 2026",
        "description": "A comprehensive deep dive into quantum algorithms and machine learning.",
        "data": {
            "general_information": {
                "type_of_activity": "Workshop",
                "title_of_activity": "Quantum AI Workshop 2026",
                "date": "25-03-2026",
                "time": "10:00 AM - 1:00 PM",
                "venue": "Audi Block 2, Central Campus",
                "collaborators": "IEEE & CUestIC",
            },
            "speakers": [
                {
                    "name": "Dr. Sarah Connor",
                    "title": "Head of Quantum Research",
                    "organization": "Cyberdyne Systems",
                    "contact": "sarah.connor@cyberdyne.io",
                },
                {
                    "name": "Prof. Alan Turing",
                    "title": "Chief Scientist",
                    "organization": "AI Frontiers",
                    "contact": "alan@frontiers.ai",
                },
            ],
            "participants": {
                "type_of_participants": "UG / PG Students & Faculty",
                "highlights": "Hands-on quantum simulator coding session.",
                "summary": "The workshop commenced at 10 AM with over 120 attendees exploring quantum gates.",
                "key_takeaways": "Practical experience with Qiskit and hybrid classical-quantum models.",
            },
            "speaker_profile": "Dr. Sarah Connor has over 15 years experience in quantum computing...",
            "impact_analysis": "96% of participants rated the session outstanding in post-event feedback.",
            "organiser": {
                "name": "Prof. H. J. Wells",
                "designation": "Associate Professor",
                "signature": "Signed",
            },
        },
    }

    res = client.post("/api/v1/documentation/reports", json=payload, headers=headers)
    assert res.status_code == 201
    res_data = res.get_json()["data"]
    report_id = res_data["id"]
    assert res_data["title"] == "Quantum AI Workshop 2026"
    assert len(res_data["data"]["speakers"]) == 2

    # 2. Get List of Reports
    res = client.get("/api/v1/documentation/reports", headers=headers)
    assert res.status_code == 200
    reports = res.get_json()["data"]
    assert any(r["id"] == report_id for r in reports)

    # 3. Get Report by ID
    res = client.get(f"/api/v1/documentation/reports/{report_id}", headers=headers)
    assert res.status_code == 200
    fetched = res.get_json()["data"]
    assert fetched["title"] == "Quantum AI Workshop 2026"
    assert fetched["data"]["general_information"]["venue"] == "Audi Block 2, Central Campus"

    # 4. Update Report Draft
    update_payload = {
        "title": "Quantum AI Workshop 2026 - Updated",
        "data": {
            **payload["data"],
            "general_information": {
                **payload["data"]["general_information"],
                "venue": "Main Auditorium, Room 101",
            },
        },
    }
    res = client.put(f"/api/v1/documentation/reports/{report_id}", json=update_payload, headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["title"] == "Quantum AI Workshop 2026 - Updated"
    assert res.get_json()["data"]["data"]["general_information"]["venue"] == "Main Auditorium, Room 101"

    # 5. AI Assist for Field (with dynamic model selection)
    with patch("app.services.ai_service.AIService.assist_field", return_value=("Polished high-impact summary", "gemini", "gemini-3.5-flash")):
        ai_res = client.post(
            f"/api/v1/documentation/reports/{report_id}/ai-assist",
            json={
                "field_key": "summary",
                "field_label": "Summary of the Activity",
                "instruction": "Make this more professional and academic",
                "current_content": "The workshop was really nice and had many students.",
                "action": "improve",
                "provider": "gemini",
            },
            headers=headers,
        )
        assert ai_res.status_code == 200
        ai_data = ai_res.get_json()["data"]
        assert ai_data["generated_text"] == "Polished high-impact summary"
        assert ai_data["provider"] == "gemini"

    # Also test GET /api/v1/documentation/ai/models
    models_res = client.get("/api/v1/documentation/ai/models", headers=headers)
    assert models_res.status_code == 200
    available_models = models_res.get_json()["data"]
    assert len(available_models) >= 2
    assert any(m["provider"] == "gemini" for m in available_models)
    assert any(m["provider"] == "grok" for m in available_models)

    # 6. Generate DOCX from Report
    gen_res = client.post(f"/api/v1/documentation/reports/{report_id}/generate-docx", headers=headers)
    assert gen_res.status_code == 200
    assert gen_res.get_json()["data"]["status"] == "generated"

    # 7. Download DOCX
    dl_res = client.get(f"/api/v1/documentation/reports/{report_id}/download-docx", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    docx_bytes = dl_res.data
    assert len(docx_bytes) > 1000

    # Verify generated DOCX structure using python-docx
    doc = docx.Document(io.BytesIO(docx_bytes))
    # Check that Table 0 contains our updated venue
    table_0_text = "".join(cell.text for row in doc.tables[0].rows for cell in row.cells)
    assert "Main Auditorium, Room 101" in table_0_text
    assert "Quantum AI Workshop 2026" in table_0_text

    # Check Table 1 has dynamic speaker rows (2 speakers)
    speaker_table_text = "".join(cell.text for row in doc.tables[1].rows for cell in row.cells)
    assert "Dr. Sarah Connor" in speaker_table_text
    assert "Prof. Alan Turing" in speaker_table_text

    # 8. Delete Report Draft
    del_res = client.delete(f"/api/v1/documentation/reports/{report_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify deletion
    res_after_del = client.get(f"/api/v1/documentation/reports/{report_id}", headers=headers)
    assert res_after_del.status_code == 404


def test_unauthorized_user_cannot_access_reports(client, doc_setup):
    headers = {"Authorization": f"Bearer {doc_setup['vol_token']}"}

    # Volunteer cannot list reports
    res = client.get("/api/v1/documentation/reports", headers=headers)
    assert res.status_code == 403

    # Volunteer cannot create reports
    res = client.post("/api/v1/documentation/reports", json={"title": "Unauthorized"}, headers=headers)
    assert res.status_code == 403


def test_poster_analysis_and_drive_images(client, doc_setup):
    headers = {"Authorization": f"Bearer {doc_setup['doc_token']}"}

    # 1. Create Event Folder and upload an image document
    folder_res = client.post(
        "/api/v1/documentation/folders",
        json={"name": "Poster Vision Test Event"},
        headers=headers,
    )
    assert folder_res.status_code == 201
    folder_id = folder_res.get_json()["data"]["id"]

    dummy_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    doc_res = client.post(
        f"/api/v1/documentation/folders/{folder_id}/documents",
        data={"file": (dummy_png, "sample_poster.png", "image/png")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.get_json()["data"]["id"]

    # 2. Test GET /api/v1/documentation/drive-images
    drive_res = client.get("/api/v1/documentation/drive-images", headers=headers)
    assert drive_res.status_code == 200
    images = drive_res.get_json()["data"]
    assert any(img["id"] == doc_id for img in images)

    # 3. Test POST /api/v1/documentation/reports/analyze-poster with document_id
    extracted_mock = {
        "title_of_activity": "Deep Learning Masterclass 2026",
        "type_of_activity": "Workshop",
        "date": "15-04-2026",
        "time": "09:30 AM - 04:30 PM",
        "venue": "Audi 3, Central Block",
        "collaborators": "CUestIC & Google Developers Group",
        "speakers": [
            {
                "name": "Dr. Geoffrey Hinton",
                "title": "Professor Emeritus",
                "organization": "University of Toronto",
                "contact": ""
            }
        ],
        "highlights": "Transformers, diffusion models, and neural architecture search.",
        "summary": "Full-day intensive hands-on masterclass.",
        "key_takeaways": "Mastering modern attention mechanisms.",
        "speaker_profile": "Pioneer in artificial neural networks."
    }

    with patch("app.services.ai_service.AIService.extract_poster_context", return_value=(extracted_mock, "gemini", "gemini-3.5-flash")):
        res = client.post(
            "/api/v1/documentation/reports/analyze-poster",
            json={"document_id": doc_id, "provider": "gemini"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["extracted_data"]["title_of_activity"] == "Deep Learning Masterclass 2026"
        assert len(data["extracted_data"]["speakers"]) == 1
        assert data["provider"] == "gemini"

    # 4. Test Multipart file upload to analyze-poster
    dummy_file = (io.BytesIO(b"\x89PNGfakeimage"), "flyer.png")
    with patch("app.services.ai_service.AIService.extract_poster_context", return_value=(extracted_mock, "gemini", "gemini-3.5-flash")):
        res = client.post(
            "/api/v1/documentation/reports/analyze-poster",
            data={"file": dummy_file, "provider": "gemini"},
            content_type="multipart/form-data",
            headers=headers,
        )
        assert res.status_code == 200
        assert res.get_json()["data"]["extracted_data"]["title_of_activity"] == "Deep Learning Masterclass 2026"

    # 5. Test AI Assist with poster_context
    rep_res = client.post("/api/v1/documentation/reports", json={"title": "Draft for Poster Test"}, headers=headers)
    rep_id = rep_res.get_json()["data"]["id"]

    with patch("app.services.ai_service.AIService.assist_field", return_value=("AI text with poster context", "gemini", "gemini-3.5-flash")) as mock_assist:
        ai_res = client.post(
            f"/api/v1/documentation/reports/{rep_id}/ai-assist",
            json={
                "field_key": "summary",
                "field_label": "Summary",
                "instruction": "Draft from poster",
                "poster_context": extracted_mock,
                "document_id": doc_id,
            },
            headers=headers,
        )
        assert ai_res.status_code == 200
        assert ai_res.get_json()["data"]["generated_text"] == "AI text with poster context"
        # Verify poster_context and image_base64 were passed to assist_field
        assert mock_assist.call_args.kwargs.get("poster_context") == extracted_mock
        assert mock_assist.call_args.kwargs.get("image_base64") is not None
