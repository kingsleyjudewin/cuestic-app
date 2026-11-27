"""Regression tests: speaker tables, Summary, Key Takeaways and Speaker Profile in the generated DOCX."""
import re

import docx

from app.services.report_generator_service import ReportGeneratorService


def _payload(speakers, **participants):
    return {
        "general_information": {"title_of_activity": "Women's Day Talk", "date": "6 March 2026"},
        "speakers": speakers,
        "speaker_profiles": [s.get("profile", "") for s in speakers],
        "speaker_profile": "\n\n".join(s.get("profile", "") for s in speakers),
        "participants": {
            "type_of_participants": "Students",
            "summary": "First summary paragraph.\nSecond summary paragraph.",
            "key_takeaways": "- One\n- Two\n- Three\n- Four\n- Five",
            **participants,
        },
    }


def _generate(tmp_path, payload):
    out = tmp_path / "r.docx"
    ReportGeneratorService.generate_report_docx(payload, str(out))
    return docx.Document(str(out))


def _spk(name, profile=""):
    return {"name": name, "title": f"{name} title", "organization": f"{name} org",
            "presentation_title": f"{name} talk", "profile": profile}


def test_summary_and_key_takeaways_are_inserted(tmp_path):
    doc = _generate(tmp_path, _payload([_spk("Alice")]))
    summary_cell = next(t for t in doc.tables if "First summary" in t.rows[0].cells[0].text).rows[0].cells[0]
    assert [p.text for p in summary_cell.paragraphs] == ["First summary paragraph.", "Second summary paragraph."]

    kt = next(t for t in doc.tables if "Key Takeaways" in t.rows[0].cells[0].text).rows[0].cells[1]
    bullets = [p.text for p in kt.paragraphs]
    assert len(bullets) == 5  # one bullet paragraph per takeaway, not merged
    assert all(b.startswith("●") for b in bullets)


def test_empty_summary_is_flagged_not_silently_blank(tmp_path):
    doc = _generate(tmp_path, _payload([_spk("Alice")], summary="", key_takeaways=""))
    text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Summary of the Activities was not provided" in text
    assert "Key Takeaways were not provided" in text


def test_each_speaker_gets_own_heading_table_and_profile(tmp_path):
    speakers = [
        _spk("Alice", "Alice is a TinyML researcher."),
        _spk("Bob", "[Insert full name, designation, and affiliation of Alice]"),  # template placeholder
        _spk("Carol", "Alice is a TinyML researcher."),  # duplicate of Alice's profile
    ]
    doc = _generate(tmp_path, _payload(speakers))
    text = "\n".join(p.text for p in doc.paragraphs)
    for n in (1, 2, 3):
        assert f"Speaker Details {n}" in text
    assert "Insert" not in text
    assert text.count("Alice is a TinyML researcher.") == 1
    assert "Bob serves as Bob title at Bob org." in text
    assert "Carol serves as Carol title at Carol org." in text


def test_corrected_sections_are_black_with_no_theme_or_hyperlink_colour(tmp_path):
    doc = _generate(tmp_path, _payload([_spk("Alice", "Alice bio."), _spk("Bob", "Bob bio.")]))
    xml = doc.element.body.xml
    seg = xml[xml.find("Speaker Details"):xml.find("Annexure")]
    assert set(re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"', seg)) == {"000000"}
    assert "themeColor" not in seg and "<w:hyperlink" not in seg
