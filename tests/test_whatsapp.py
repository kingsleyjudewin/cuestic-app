import urllib.parse
from datetime import timedelta
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.message_log import MessageLog
from app.utils.datetime_utils import utc_now
from app.extensions import db


def create_assignment_for_member(event, member, admin_user):
    task = Task(
        event_id=event.id,
        title="Prepare Event Stage Lighting",
        description="Arrange spotlights and sound checks in main hall",
        priority="urgent",
        deadline=utc_now() + timedelta(days=2),
        created_by=admin_user["user"].id,
    )
    db.session.add(task)
    db.session.flush()

    assignment = TaskAssignment(
        task_id=task.id,
        member_id=member.id,
        assigned_by=admin_user["user"].id,
        status=TaskAssignment.STATUS_AWAITING_CONFIRMATION,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


def test_generate_encoded_whatsapp_link(client, admin_user, sample_event, seed_members):
    """
    Test generating click-to-chat URL with normalized phone number and URL-encoded message text.
    Format: https://wa.me/{normalized_phone}?text={url_encoded_message}
    """
    assignment = create_assignment_for_member(sample_event, seed_members["m1"], admin_user)

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/whatsapp-link",
        headers=admin_user["headers"]
    )
    assert response.status_code == 200
    data = response.get_json()["data"]

    # Verify normalized phone number in wa.me link (no +, dashes or spaces)
    assert data["wa_phone"] == "919876500001"
    url = data["whatsapp_url"]
    assert url.startswith("https://wa.me/919876500001?text=")

    # Verify query parameter is properly URL encoded
    parsed_url = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed_url.query)
    assert "text" in params
    decoded_text = params["text"][0]

    # Verify personalized content
    assert "Hi Ananya Sharma" in decoded_text
    assert sample_event.name in decoded_text
    assert "Prepare Event Stage Lighting" in decoded_text
    assert "Urgent" in decoded_text
    assert "Department Club Team" in decoded_text

    # Verify draft was recorded in MessageLog
    log_id = data["message_log_id"]
    log = db.session.get(MessageLog, log_id)
    assert log is not None
    assert log.status == MessageLog.STATUS_DRAFTED


def test_reject_messaging_when_consent_withdrawn(client, admin_user, sample_event, seed_members):
    """
    Test that if a member has opted out of WhatsApp (whatsapp_opt_in=False),
    generating WhatsApp messages or links is rejected with a validation error.
    """
    # m3 has whatsapp_opt_in = False
    assignment = create_assignment_for_member(sample_event, seed_members["m3"], admin_user)

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/whatsapp-link",
        headers=admin_user["headers"]
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "opted out" in data["error"]["message"].lower()


def test_reject_messaging_inactive_member(client, admin_user, sample_event, seed_members):
    """Test rejecting WhatsApp message generation for inactive members."""
    # m4 is inactive
    assignment = create_assignment_for_member(sample_event, seed_members["m4"], admin_user)

    response = client.post(
        f"/api/v1/assignments/{assignment.id}/whatsapp-link",
        headers=admin_user["headers"]
    )
    assert response.status_code == 400
    assert "inactive" in response.get_json()["error"]["message"].lower()


def test_link_opened_does_not_imply_acceptance(client, admin_user, sample_event, seed_members):
    """
    Test that recording a 'link_opened' action updates MessageLog
    but NEVER changes TaskAssignment status to accepted!
    """
    assignment = create_assignment_for_member(sample_event, seed_members["m1"], admin_user)

    # Generate link
    res1 = client.post(f"/api/v1/assignments/{assignment.id}/whatsapp-link", headers=admin_user["headers"])
    log_id = res1.get_json()["data"]["message_log_id"]

    # Record link_opened
    res2 = client.post(
        f"/api/v1/assignments/{assignment.id}/message-action",
        headers=admin_user["headers"],
        json={"message_log_id": log_id, "action": "link_opened"}
    )
    assert res2.status_code == 200

    # Verify assignment status is STILL awaiting_confirmation
    refreshed_assignment = db.session.get(TaskAssignment, assignment.id)
    assert refreshed_assignment.status == TaskAssignment.STATUS_AWAITING_CONFIRMATION


def test_record_marked_sent_action_and_history(client, admin_user, sample_event, seed_members):
    """Test explicitly recording marked_sent and querying message history."""
    assignment = create_assignment_for_member(sample_event, seed_members["m1"], admin_user)

    res1 = client.post(f"/api/v1/assignments/{assignment.id}/whatsapp-link", headers=admin_user["headers"])
    log_id = res1.get_json()["data"]["message_log_id"]

    # Record marked_sent
    res2 = client.post(
        f"/api/v1/assignments/{assignment.id}/message-action",
        headers=admin_user["headers"],
        json={"message_log_id": log_id, "action": "marked_sent"}
    )
    assert res2.status_code == 200
    assert res2.get_json()["data"]["status"] == "marked_sent"

    # Query message history
    res3 = client.get(
        f"/api/v1/assignments/{assignment.id}/message-history",
        headers=admin_user["headers"]
    )
    assert res3.status_code == 200
    history = res3.get_json()["data"]
    assert len(history) == 1
    assert history[0]["status"] == "marked_sent"
    assert history[0]["action_recorded_at"] is not None
