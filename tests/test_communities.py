import pytest
from app import db
from app.models.user import User, ApiToken
from app.models.team import Team
from app.models.member import Member
from app.models.community import Community, CommunityChannel, ChatMessage
from app.services.community_service import provision_default_communities
from app.utils.datetime_utils import utc_now
from datetime import timedelta


@pytest.fixture
def club_community_setup(app):
    """Seed the exact real club users, teams, and members for the community tests."""
    with app.app_context():
        # Teams
        t_vol = Team(name="Volunteering", slug="volunteering", description="Volunteering team")
        t_doc = Team(name="Documentation", slug="documentation", description="Docs team")
        t_med = Team(name="Media", slug="media", description="Media team")
        db.session.add_all([t_vol, t_doc, t_med])
        db.session.commit()

        # Users & Members
        accounts = [
            # President
            ("clubadmin", "AdminPass123!Secure", "president", None, None),
            # Volunteering
            ("sagar.cu", "sagar.cu@123", "member", "Sagar CU", t_vol.id),
            ("kanishk", "kanishk@123", "member", "Kanishk M", t_vol.id),
            # Documentation
            ("surasmita", "surasmita@123", "member", "Surasmita", t_doc.id),
            ("salomi", "salomi@123", "member", "Salomi", t_doc.id),
            ("pooja", "pooja@123", "member", "Pooja", t_doc.id),
            ("manyatha", "manyatha@123", "member", "Manyatha", t_doc.id),
            # Media
            ("nivin.cu", "nivin.cu@123", "member", "Nivin CU", t_med.id),
            ("aleena.cuestic", "aleena.cuestic@123", "member", "Aleena Cuestic", t_med.id),
        ]

        user_tokens = {}
        for idx, (username, pwd, role, full_name, team_id) in enumerate(accounts):
            u = User(
                username=username,
                email=f"{username}@club.edu",
                role=role,
                is_active=True
            )
            u.set_password(pwd)
            db.session.add(u)
            db.session.flush()

            if full_name:
                m = Member(
                    full_name=full_name,
                    registration_number=f"REG-2026-{100 + idx}",
                    class_name="3rd Year ECE",
                    section="A",
                    phone_number=f"+919876543{idx:03d}",
                    team_id=team_id,
                    linked_user_id=u.id,
                    is_active=True
                )
                db.session.add(m)

            token_obj, raw_token = ApiToken.create_token(
                user_id=u.id,
                expires_at=utc_now() + timedelta(days=7),
                name="Suite Token"
            )
            db.session.add(token_obj)
            user_tokens[username] = raw_token

        db.session.commit()

        # Provision Discord communities and populate members
        provision_default_communities()

        return {
            "teams": {"volunteering": t_vol, "documentation": t_doc, "media": t_med},
            "tokens": user_tokens
        }


def test_president_sees_all_communities(client, club_community_setup):
    """President should have access to and see all communities."""
    token = club_community_setup["tokens"]["clubadmin"]
    resp = client.get("/api/v1/communities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    slugs = [c["slug"] for c in data]
    assert "volunteering-community" in slugs
    assert "documentation-community" in slugs
    assert "media-community" in slugs


def test_volunteering_member_only_sees_volunteering_community(client, club_community_setup):
    """Volunteering member (Sagar) only sees their own team community."""
    token = club_community_setup["tokens"]["sagar.cu"]
    resp = client.get("/api/v1/communities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    slugs = [c["slug"] for c in data]
    assert "volunteering-community" in slugs
    assert "documentation-community" not in slugs
    assert "media-community" not in slugs


def test_documentation_member_only_sees_documentation_community(client, club_community_setup):
    """Documentation member (Surasmita) only sees documentation community."""
    token = club_community_setup["tokens"]["surasmita"]
    resp = client.get("/api/v1/communities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    slugs = [c["slug"] for c in data]
    assert "documentation-community" in slugs
    assert "volunteering-community" not in slugs
    assert "media-community" not in slugs


def test_cross_team_access_denied(client, club_community_setup):
    """Members cannot access or post messages into other team communities."""
    sagar_token = club_community_setup["tokens"]["sagar.cu"]
    surasmita_token = club_community_setup["tokens"]["surasmita"]

    with client.application.app_context():
        doc_comm = Community.query.filter_by(slug="documentation-community").first()
        vol_comm = Community.query.filter_by(slug="volunteering-community").first()
        doc_ch = CommunityChannel.query.filter_by(community_id=doc_comm.id, name="general").first()
        vol_ch = CommunityChannel.query.filter_by(community_id=vol_comm.id, name="general").first()

    # Sagar (Volunteering) tries to access Documentation Community -> 403 Forbidden
    resp = client.get(
        f"/api/v1/communities/{doc_comm.id}",
        headers={"Authorization": f"Bearer {sagar_token}"}
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.get_json()["error"]["message"]

    # Sagar tries to post into Documentation Channel -> 403 Forbidden
    resp = client.post(
        f"/api/v1/communities/{doc_comm.id}/channels/{doc_ch.id}/messages",
        json={"content": "Unauthorized post attempt"},
        headers={"Authorization": f"Bearer {sagar_token}"}
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.get_json()["error"]["message"]

    # Surasmita (Documentation) tries to access Volunteering Community -> 403 Forbidden
    resp = client.get(
        f"/api/v1/communities/{vol_comm.id}",
        headers={"Authorization": f"Bearer {surasmita_token}"}
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.get_json()["error"]["message"]


def test_team_members_chat_end_to_end(client, club_community_setup):
    """Actual team members chat in their respective communities successfully."""
    sagar_token = club_community_setup["tokens"]["sagar.cu"]
    kanishk_token = club_community_setup["tokens"]["kanishk"]
    president_token = club_community_setup["tokens"]["clubadmin"]

    with client.application.app_context():
        vol_comm = Community.query.filter_by(slug="volunteering-community").first()
        chat_ch = CommunityChannel.query.filter_by(community_id=vol_comm.id, name="volunteers-chat").first()

    # 1. Sagar sends message
    resp1 = client.post(
        f"/api/v1/communities/{vol_comm.id}/channels/{chat_ch.id}/messages",
        json={"content": "Hey volunteering team! Auditorium hall is prepped."},
        headers={"Authorization": f"Bearer {sagar_token}"}
    )
    assert resp1.status_code == 201
    msg1 = resp1.get_json()["data"]
    assert msg1["sender_name"] == "Sagar CU"

    # 2. Kanishk responds
    resp2 = client.post(
        f"/api/v1/communities/{vol_comm.id}/channels/{chat_ch.id}/messages",
        json={"content": "Got it Sagar, badge distribution counters are ready at the entrance."},
        headers={"Authorization": f"Bearer {kanishk_token}"}
    )
    assert resp2.status_code == 201
    msg2 = resp2.get_json()["data"]
    assert msg2["sender_name"] == "Kanishk M"

    # 3. President oversees and broadcasts encouragement
    resp3 = client.post(
        f"/api/v1/communities/{vol_comm.id}/channels/{chat_ch.id}/messages",
        json={"content": "Great coordination Sagar and Kanishk! Keep up the good work."},
        headers={"Authorization": f"Bearer {president_token}"}
    )
    assert resp3.status_code == 201

    # 4. Fetch message history
    history_resp = client.get(
        f"/api/v1/communities/{vol_comm.id}/channels/{chat_ch.id}/messages",
        headers={"Authorization": f"Bearer {sagar_token}"}
    )
    assert history_resp.status_code == 200
    messages = history_resp.get_json()["data"]
    contents = [m["content"] for m in messages]
    assert "Hey volunteering team! Auditorium hall is prepped." in contents
    assert "Got it Sagar, badge distribution counters are ready at the entrance." in contents
    assert "Great coordination Sagar and Kanishk! Keep up the good work." in contents


def test_channel_creation_in_community(client, club_community_setup):
    """Members can create channels / group chats in their authorized community."""
    sagar_token = club_community_setup["tokens"]["sagar.cu"]

    with client.application.app_context():
        vol_comm = Community.query.filter_by(slug="volunteering-community").first()

    resp = client.post(
        f"/api/v1/communities/{vol_comm.id}/channels",
        json={
            "name": "stage-setup",
            "topic": "Coordination channel for stage audio and seating",
            "channel_type": "group_chat"
        },
        headers={"Authorization": f"Bearer {sagar_token}"}
    )
    assert resp.status_code == 201
    ch_data = resp.get_json()["data"]
    assert ch_data["name"] == "stage-setup"
    assert ch_data["channel_type"] == "group_chat"
