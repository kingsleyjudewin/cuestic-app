import pytest
from app.models.user import User
from app.models.mc_script import McScript, McScriptSegment, McTemplate, McTemplateSegment
from app.services.mc_template_service import McTemplateService
from app.services.mc_script_service import McScriptService
from app.services.mc_ai_service import MCAssistantService
from app.extensions import db


def test_seed_templates_and_event_catalog(app):
    """Verify that default templates are seeded and event types catalog is loaded."""
    with app.app_context():
        # Seed templates if running in fresh test DB
        McTemplateService.seed_default_templates()
        catalog = McTemplateService.get_event_types_catalog()
        assert len(catalog) >= 15
        assert any(c["event_type"] == "Technical Talk" for c in catalog)
        assert any(c["event_type"] == "Valedictory Function" for c in catalog)

        # Check seeded database templates
        templates = McTemplate.query.all()
        assert len(templates) >= 15
        tech_talk = McTemplate.query.filter_by(event_type="Technical Talk").first()
        assert tech_talk is not None
        assert len(tech_talk.segments) >= 10


def test_create_script_from_template_and_segments_crud(app, admin_user, member_user):
    """Test creating a script populated from a template, and performing visual builder CRUD."""
    with app.app_context():
        McTemplateService.seed_default_templates()
        admin = User.query.filter_by(username="test_admin").first()
        member = User.query.filter_by(username="test_member").first()

        # 1. Create script using 'Technical Talk' template
        tech_template = McTemplate.query.filter_by(event_type="Technical Talk").first()
        script = McScriptService.create_script(
            {
                "title": "IEEE Quantum Computing Talk 2026",
                "event_type": "Technical Talk",
                "template_id": tech_template.id if tech_template else None,
                "venue": "Audi Block 2",
                "anchors": [{"name": "Merrick Dias"}, {"name": "Qurrath Ul Ain"}],
            },
            member,
        )

        assert script.id is not None
        assert script.event_type == "Technical Talk"

        # Check segments were instantiated
        segments = McScriptSegment.query.filter_by(script_id=script.id).order_by(McScriptSegment.sequence_order).all()
        assert len(segments) >= 10
        seg1 = segments[0]
        assert seg1.sequence_order == 1

        # 2. Add a custom segment
        new_seg = McScriptService.add_segment(
            script.id,
            {
                "segment_type": "custom",
                "title": "Special Drone Demo",
                "assigned_mc": "Merrick Dias",
                "stage_directions": "[Lights dim as drone takes off]",
                "dialogue": "(Merrick Dias): Behold the autonomous flight demo!",
            },
            member,
        )
        assert new_seg["title"] == "Special Drone Demo"

        # 3. Update segment
        updated_seg = McScriptService.update_segment(
            script.id,
            new_seg["id"],
            {"title": "Autonomous Drone Showcase"},
            member,
        )
        assert updated_seg["title"] == "Autonomous Drone Showcase"

        # 4. Duplicate segment
        dup_seg = McScriptService.duplicate_segment(script.id, new_seg["id"], member)
        assert "Copy" in dup_seg["title"]

        # 5. Reorder segments
        all_segs = McScriptSegment.query.filter_by(script_id=script.id).all()
        reversed_ids = [s.id for s in reversed(all_segs)]
        reordered = McScriptService.reorder_segments(script.id, reversed_ids, member)
        assert reordered[0]["id"] == reversed_ids[0]

        # 6. Delete duplicated segment
        deleted = McScriptService.delete_segment(script.id, dup_seg["id"], member)
        assert deleted is True

        # 7. Auto assign MCs
        auto_segs = McScriptService.auto_assign_mcs(script.id, member)
        assert len(auto_segs) > 0
        assigned_names = set(s["assigned_mc"] for s in auto_segs)
        assert "Merrick Dias" in assigned_names or "Qurrath Ul Ain" in assigned_names

        # 8. Save script as custom template
        custom_template = McTemplateService.save_script_as_template(
            script.id,
            "Custom Quantum Symposium Flow",
            "Reordered programme flow for quantum tech talk",
            member,
        )
        assert custom_template["id"] is not None
        assert custom_template["name"] == "Custom Quantum Symposium Flow"
        assert len(custom_template["segments"]) == len(reordered) - 1  # Minus deleted


def test_script_preflight_validation(app, member_user):
    """Test script preflight checklist validation."""
    with app.app_context():
        member = User.query.filter_by(username="test_member").first()

        script = McScriptService.create_script(
            {
                "title": "Validating Script",
                "venue": "Hall A",
                "anchors": [{"name": "Anchor 1"}],
            },
            member,
        )

        val = McScriptService.validate_script(script.id, member)
        assert "is_valid" in val
        assert isinstance(val["warnings"], list)
